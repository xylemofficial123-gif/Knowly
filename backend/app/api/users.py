"""
User and Group management API.

Three-tier roles:
  admin       – manages users, groups, all content
  group_admin – manages their own groups
  member      – personal docs only

Endpoints:
  GET/POST      /api/users
  GET/PUT/DELETE /api/users/{email}
  GET/POST      /api/groups
  GET/PUT/DELETE /api/groups/{group_id}
  GET/POST      /api/groups/{group_id}/members
  DELETE        /api/groups/{group_id}/members/{user_email}
"""

import logging
import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.core.acl import invalidate_user_cache
from app.models import User, Group, GroupMembership

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["users-groups"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    display_name: str = ""
    role: str = "member"  # admin | group_admin | member


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    created_by_email: str = ""


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class MemberAdd(BaseModel):
    user_email: str
    role: str = "member"  # group_admin | member


# ── User endpoints ────────────────────────────────────────────────────────────

@router.get("/users")
def list_users(limit: int = 100, offset: int = 0):
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
        total = db.query(User).count()
        return {
            "users": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "display_name": u.display_name or "",
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else "",
                }
                for u in users
            ],
            "total": total,
        }
    finally:
        db.close()


@router.post("/users", status_code=201)
def create_user(body: UserCreate):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == body.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="User already exists")

        if body.role not in ("admin", "group_admin", "member"):
            raise HTTPException(status_code=400, detail="role must be admin, group_admin, or member")

        user = User(
            email=body.email,
            display_name=body.display_name or body.email.split("@")[0],
            role=body.role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        invalidate_user_cache(body.email)
        return {"id": str(user.id), "email": user.email, "role": user.role}
    finally:
        db.close()


@router.get("/users/{email:path}")
def get_user(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Include group memberships
        memberships = db.query(GroupMembership).filter(GroupMembership.user_email == email).all()
        group_ids = [str(m.group_id) for m in memberships]
        groups = db.query(Group).filter(Group.id.in_([m.group_id for m in memberships])).all() if memberships else []
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name or "",
            "role": user.role,
            "groups": [{"id": str(g.id), "name": g.name, "role": next((m.role for m in memberships if str(m.group_id) == str(g.id)), "member")} for g in groups],
            "created_at": user.created_at.isoformat() if user.created_at else "",
        }
    finally:
        db.close()


@router.put("/users/{email:path}")
def update_user(email: str, body: UserUpdate):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if body.role is not None:
            if body.role not in ("admin", "group_admin", "member"):
                raise HTTPException(status_code=400, detail="role must be admin, group_admin, or member")
            user.role = body.role
        if body.display_name is not None:
            user.display_name = body.display_name

        user.updated_at = datetime.datetime.utcnow()
        db.commit()
        invalidate_user_cache(email)
        return {"email": user.email, "role": user.role, "display_name": user.display_name}
    finally:
        db.close()


@router.delete("/users/{email:path}", status_code=204)
def delete_user(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        db.delete(user)
        db.commit()
        invalidate_user_cache(email)
    finally:
        db.close()


# ── Group endpoints ───────────────────────────────────────────────────────────

@router.get("/groups")
def list_groups(limit: int = 100, offset: int = 0):
    db = SessionLocal()
    try:
        groups = db.query(Group).order_by(Group.created_at.desc()).offset(offset).limit(limit).all()
        total = db.query(Group).count()
        result = []
        for g in groups:
            member_count = db.query(GroupMembership).filter(GroupMembership.group_id == g.id).count()
            result.append({
                "id": str(g.id),
                "name": g.name,
                "description": g.description or "",
                "created_by_email": g.created_by_email or "",
                "member_count": member_count,
                "created_at": g.created_at.isoformat() if g.created_at else "",
            })
        return {"groups": result, "total": total}
    finally:
        db.close()


@router.post("/groups", status_code=201)
def create_group(body: GroupCreate):
    db = SessionLocal()
    try:
        existing = db.query(Group).filter(Group.name == body.name).first()
        if existing:
            raise HTTPException(status_code=409, detail="Group with this name already exists")

        group = Group(
            name=body.name,
            description=body.description,
            created_by_email=body.created_by_email,
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        # Auto-add creator as group_admin if provided
        if body.created_by_email:
            membership = GroupMembership(
                user_email=body.created_by_email,
                group_id=group.id,
                role="group_admin",
            )
            db.add(membership)
            db.commit()
            invalidate_user_cache(body.created_by_email)

        return {"id": str(group.id), "name": group.name}
    finally:
        db.close()


@router.get("/groups/{group_id}")
def get_group(group_id: str):
    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        memberships = db.query(GroupMembership).filter(GroupMembership.group_id == group_id).all()
        return {
            "id": str(group.id),
            "name": group.name,
            "description": group.description or "",
            "created_by_email": group.created_by_email or "",
            "members": [
                {"user_email": m.user_email, "role": m.role, "added_at": m.added_at.isoformat() if m.added_at else ""}
                for m in memberships
            ],
            "created_at": group.created_at.isoformat() if group.created_at else "",
        }
    finally:
        db.close()


@router.put("/groups/{group_id}")
def update_group(group_id: str, body: GroupUpdate):
    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        if body.name is not None:
            group.name = body.name
        if body.description is not None:
            group.description = body.description
        group.updated_at = datetime.datetime.utcnow()
        db.commit()
        return {"id": str(group.id), "name": group.name}
    finally:
        db.close()


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: str):
    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        # Invalidate cache for all members before deleting
        memberships = db.query(GroupMembership).filter(GroupMembership.group_id == group_id).all()
        for m in memberships:
            invalidate_user_cache(m.user_email)
        db.delete(group)
        db.commit()
    finally:
        db.close()


# ── Group membership endpoints ────────────────────────────────────────────────

@router.get("/groups/{group_id}/members")
def list_group_members(group_id: str):
    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        memberships = db.query(GroupMembership).filter(GroupMembership.group_id == group_id).all()
        return {
            "group_id": group_id,
            "group_name": group.name,
            "members": [
                {"user_email": m.user_email, "role": m.role, "added_at": m.added_at.isoformat() if m.added_at else ""}
                for m in memberships
            ],
        }
    finally:
        db.close()


@router.post("/groups/{group_id}/members", status_code=201)
def add_group_member(group_id: str, body: MemberAdd):
    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        existing = (
            db.query(GroupMembership)
            .filter(GroupMembership.group_id == group_id, GroupMembership.user_email == body.user_email)
            .first()
        )
        if existing:
            # Update role if already a member
            existing.role = body.role
            db.commit()
            invalidate_user_cache(body.user_email)
            return {"user_email": body.user_email, "role": body.role, "updated": True}

        if body.role not in ("group_admin", "member"):
            raise HTTPException(status_code=400, detail="role must be group_admin or member")

        # Auto-create User record if it doesn't exist
        user = db.query(User).filter(User.email == body.user_email).first()
        if not user:
            user = User(
                email=body.user_email,
                display_name=body.user_email.split("@")[0],
                role="member",
            )
            db.add(user)

        membership = GroupMembership(
            user_email=body.user_email,
            group_id=group_id,
            role=body.role,
        )
        db.add(membership)
        db.commit()
        invalidate_user_cache(body.user_email)
        return {"user_email": body.user_email, "group_id": group_id, "role": body.role}
    finally:
        db.close()


@router.delete("/groups/{group_id}/members/{user_email:path}", status_code=204)
def remove_group_member(group_id: str, user_email: str):
    db = SessionLocal()
    try:
        membership = (
            db.query(GroupMembership)
            .filter(GroupMembership.group_id == group_id, GroupMembership.user_email == user_email)
            .first()
        )
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
        db.delete(membership)
        db.commit()
        invalidate_user_cache(user_email)
    finally:
        db.close()
