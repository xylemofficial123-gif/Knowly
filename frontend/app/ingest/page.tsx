"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuditEntry {
  id: string;
  user_email: string;
  query: string;
  result_count: string;
  timestamp: string;
}

interface ReviewItem {
  id: string;
  proposed_decision: string;
  proposed_rationale: string;
  confidence: number;
  decision_type: string;
  trigger_phrase: string;
  source_url: string;
  status: string;
  created_at: string;
}

interface FeedbackItem {
  id: string;
  query: string;
  rating: string;
  comment: string;
  agent: string;
  query_type: string;
  confidence: number;
  user_email: string;
  created_at: string;
}

interface Metrics {
  overview: {
    total_queries: number;
    queries_today: number;
    queries_this_week: number;
    unique_users: number;
    avg_confidence: number;
    avg_response_time_ms: number;
  };
  feedback: {
    total: number;
    helpful: number;
    not_helpful: number;
    helpfulness_rate: number;
  };
  deflection?: {
    rate: number;
    checks_total: number;
    matches_found: number;
    window_days: number;
  };
  adherence?: {
    rate: number;
    total_decisions: number;
    active_decisions: number;
    reversed_last_30d: number;
  };
  agent_usage: Record<string, number>;
  query_type_usage: Record<string, number>;
  daily_usage: { date: string; count: number }[];
}

interface IngestionSettings {
  enabled_sources: string[];
  google_drive_folder_ids: string[];
}

interface DriveFolder {
  id: string;
  name: string;
}

interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: string;
  groups: { id: string; name: string; role: string }[];
}

interface GroupRecord {
  id: string;
  name: string;
  description: string;
  created_by_email: string;
  member_count: number;
  members?: { user_email: string; role: string }[];
}
interface GroupDocumentRecord {
  id: string;
  title: string;
  source: string;
  url: string;
  doc_status: string;
  updated_at: string;
  created_at: string;
}

export default function AdminPage() {
  const { user } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const currentUserEmail = user?.emailAddresses?.[0]?.emailAddress ?? "";

  const authedFetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const token = await getToken();
    const headers = new Headers(init.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  };

  const [tab, setTab] = useState<"metrics" | "audit" | "review" | "feedback" | "ingestion" | "users" | "groups" | "upload" | "connections" | "no-index">(
    "ingestion"
  );

  // Connections state
  interface ClickUpStatus {
    connected: boolean;
    workspace_name?: string;
    team_id?: string;
    connected_at?: string;
  }
  interface GoogleStatus {
    connected: boolean;
    connected_email?: string;
    connected_at?: string;
  }
  interface SlackStatus {
    connected: boolean;
    workspace_name?: string;
    workspace_id?: string;
    connected_by?: string;
    connected_at?: string;
  }
  interface MeUser {
    role: string;
    can_connect_sources: boolean;
  }
  const [me, setMe] = useState<MeUser | null>(null);

  const [clickupStatus, setClickupStatus] = useState<ClickUpStatus | null>(null);
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(null);
  const [slackStatus, setSlackStatus] = useState<SlackStatus | null>(null);
  const [connectionsLoading, setConnectionsLoading] = useState(false);
  const [disconnectingSlack, setDisconnectingSlack] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [settings, setSettings] = useState<IngestionSettings | null>(null);
  const [availableFolders, setAvailableFolders] = useState<DriveFolder[]>([]);
  const [newFolderId, setNewFolderId] = useState("");
  const [folderSearch, setFolderSearch] = useState("");
  const [loading, setLoading] = useState(false);

  // Users & Groups state
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [groups, setGroups] = useState<GroupRecord[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<GroupRecord | null>(null);
  const [groupDocuments, setGroupDocuments] = useState<GroupDocumentRecord[]>([]);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserRole, setNewUserRole] = useState("member");
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupDesc, setNewGroupDesc] = useState("");
  const [addMemberEmail, setAddMemberEmail] = useState("");
  const [addMemberRole, setAddMemberRole] = useState("member");

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadScope, setUploadScope] = useState("private");
  const [uploadGroupId, setUploadGroupId] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadSharedWith, setUploadSharedWith] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");

  // No-Index Zones state
  interface ExclusionRuleRecord {
    id: string;
    source_type: string;
    identifier: string;
    name: string;
    reason: string;
    created_by: string;
    created_at: string;
  }
  const [exclusionRules, setExclusionRules] = useState<ExclusionRuleRecord[]>([]);
  const [newRuleSource, setNewRuleSource] = useState("slack");
  const [newRuleIdentifier, setNewRuleIdentifier] = useState("");
  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleReason, setNewRuleReason] = useState("");
  const [selfRole, setSelfRole] = useState<string | null>(null);
  const currentUserRole = selfRole || users.find(
    (u) => u.email.toLowerCase() === currentUserEmail.toLowerCase()
  )?.role || "member";
  const canManageUsers = currentUserRole === "admin";
  const canManageSources = currentUserRole === "admin";
  const canUploadGroup = currentUserRole === "admin" || currentUserRole === "group_admin";
  const canUploadPublic = currentUserRole === "admin";
  const canManageSelectedGroup =
    currentUserRole === "admin" ||
    Boolean(
      selectedGroup?.members?.some(
        (m) =>
          m.user_email.toLowerCase() === currentUserEmail.toLowerCase() &&
          m.role === "group_admin"
      )
    );

  const fetchExclusionRules = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/exclusion-rules`);
      const data = await res.json();
      setExclusionRules(data.rules || []);
    } catch (e) {
      console.error("Failed to fetch exclusion rules:", e);
    } finally {
      setLoading(false);
    }
  };

  const createExclusionRule = async () => {
    if (!newRuleIdentifier.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/admin/exclusion-rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: newRuleSource,
          identifier: newRuleIdentifier.trim(),
          name: newRuleName.trim(),
          reason: newRuleReason.trim(),
        }),
      });
      if (res.ok) {
        setNewRuleIdentifier("");
        setNewRuleName("");
        setNewRuleReason("");
        fetchExclusionRules();
      }
    } catch (e) {
      console.error("Failed to create exclusion rule:", e);
    }
  };

  const deleteExclusionRule = async (ruleId: string) => {
    try {
      await fetch(`${API_URL}/api/admin/exclusion-rules/${ruleId}`, { method: "DELETE" });
      fetchExclusionRules();
    } catch (e) {
      console.error("Failed to delete exclusion rule:", e);
    }
  };

  const fetchAuditLog = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/audit-log`);
      const data = await res.json();
      setAuditLog(data.entries || []);
    } catch (e) {
      console.error("Failed to fetch audit log:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchReviewQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/admin/review-queue?status=pending`
      );
      const data = await res.json();
      setReviewQueue(data.items || []);
    } catch (e) {
      console.error("Failed to fetch review queue:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchFeedback = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/feedback`);
      const data = await res.json();
      setFeedbackList(data.items || []);
    } catch (e) {
      console.error("Failed to fetch feedback:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/metrics`);
      const data = await res.json();
      setMetrics(data);
    } catch (e) {
      console.error("Failed to fetch metrics:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/settings`);
      const data = await res.json();
      setSettings(data);
    } catch (e) {
      console.error("Failed to fetch settings:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableFolders = async () => {
    // Avoid noisy 500s when Drive is disabled or Google isn't connected.
    const driveEnabled = Boolean(settings?.enabled_sources?.includes("drive"));
    if (!driveEnabled) {
      setAvailableFolders([]);
      return;
    }

    try {
      const statusUrl = currentUserEmail
        ? `${API_URL}/api/oauth/google/status?user_email=${encodeURIComponent(currentUserEmail)}`
        : `${API_URL}/api/oauth/google/status`;
      const statusRes = await fetch(statusUrl);
      const statusData = await statusRes.json();
      if (!statusData?.connected) {
        setAvailableFolders([]);
        return;
      }

      const url = currentUserEmail
        ? `${API_URL}/api/ingest/drive/folders?user_email=${encodeURIComponent(currentUserEmail)}`
        : `${API_URL}/api/ingest/drive/folders`;
      const res = await fetch(url);
      const data = await res.json();
      setAvailableFolders(data.folders || []);
    } catch (e) {
      console.error("Failed to fetch available folders:", e);
    }
  };

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`${API_URL}/api/users`);
      const data = await res.json();
      setUsers(data.users || []);
    } catch (e) {
      console.error("Failed to fetch users:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSelfRole = async () => {
    if (!currentUserEmail) return;
    try {
      // /users/me returns the authenticated user's role + a `can_connect_sources`
      // flag that's true when role is admin/group_admin OR they're a group_admin
      // in at least one group. Backend authoritative; frontend uses the flag
      // to gate the "Connect Google" UI.
      const res = await authedFetch(`${API_URL}/api/users/me`);
      if (!res.ok) return;
      const data = await res.json();
      if (data?.role) setSelfRole(data.role);
      setMe({
        role: data?.role || "member",
        can_connect_sources: !!data?.can_connect_sources,
      });
    } catch (e) {
      console.error("Failed to fetch current user role:", e);
    }
  };

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`${API_URL}/api/groups`);
      const data = await res.json();
      setGroups(data.groups || []);
    } catch (e) {
      console.error("Failed to fetch groups:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchGroupDetail = async (groupId: string) => {
    try {
      const res = await authedFetch(`${API_URL}/api/groups/${groupId}`);
      const data = await res.json();
      setSelectedGroup(data);
      const docsRes = await authedFetch(`${API_URL}/api/groups/${groupId}/documents?limit=100`);
      const docsData = await docsRes.json();
      setGroupDocuments(docsData.documents || []);
    } catch (e) {
      console.error("Failed to fetch group detail:", e);
      setGroupDocuments([]);
    }
  };

  const createUser = async () => {
    if (!canManageUsers) return;
    if (!newUserEmail.trim()) return;
    try {
      await authedFetch(`${API_URL}/api/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: newUserEmail.trim(), role: newUserRole }),
      });
      setNewUserEmail("");
      fetchUsers();
    } catch (e) {
      console.error("Failed to create user:", e);
    }
  };

  const updateUserRole = async (email: string, role: string) => {
    if (!canManageUsers) return;
    try {
      await authedFetch(`${API_URL}/api/users/${encodeURIComponent(email)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      fetchUsers();
    } catch (e) {
      console.error("Failed to update user role:", e);
    }
  };

  const deleteUser = async (email: string) => {
    if (!canManageUsers) return;
    if (!confirm(`Delete user ${email}?`)) return;
    try {
      await authedFetch(`${API_URL}/api/users/${encodeURIComponent(email)}`, { method: "DELETE" });
      fetchUsers();
    } catch (e) {
      console.error("Failed to delete user:", e);
    }
  };

  const createGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      await authedFetch(`${API_URL}/api/groups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newGroupName.trim(), description: newGroupDesc }),
      });
      setNewGroupName("");
      setNewGroupDesc("");
      fetchGroups();
    } catch (e) {
      console.error("Failed to create group:", e);
    }
  };

  const deleteGroup = async (groupId: string) => {
    if (!confirm("Delete this group?")) return;
    try {
      await authedFetch(`${API_URL}/api/groups/${groupId}`, { method: "DELETE" });
      setSelectedGroup(null);
      setGroupDocuments([]);
      fetchGroups();
    } catch (e) {
      console.error("Failed to delete group:", e);
    }
  };

  const addMember = async (groupId: string) => {
    if (!addMemberEmail.trim()) return;
    try {
      await authedFetch(`${API_URL}/api/groups/${groupId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_email: addMemberEmail.trim(), role: addMemberRole }),
      });
      setAddMemberEmail("");
      fetchGroupDetail(groupId);
    } catch (e) {
      console.error("Failed to add member:", e);
    }
  };

  const removeMember = async (groupId: string, email: string) => {
    try {
      await authedFetch(`${API_URL}/api/groups/${groupId}/members/${encodeURIComponent(email)}`, {
        method: "DELETE",
      });
      fetchGroupDetail(groupId);
    } catch (e) {
      console.error("Failed to remove member:", e);
    }
  };

  const deleteGroupDocument = async (groupId: string, documentId: string) => {
    if (!confirm("Delete this document from the group knowledge base?")) return;
    try {
      await authedFetch(`${API_URL}/api/groups/${groupId}/documents/${documentId}`, {
        method: "DELETE",
      });
      fetchGroupDetail(groupId);
    } catch (e) {
      console.error("Failed to delete group document:", e);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) {
      setUploadStatus("Please select a file.");
      return;
    }
    if (!currentUserEmail.trim()) {
      setUploadStatus("Unable to resolve signed-in user email.");
      return;
    }
    if (uploadScope === "group" && !uploadGroupId) {
      setUploadStatus("Please select a group for group-scoped upload.");
      return;
    }
    if (uploadScope === "group" && !canUploadGroup) {
      setUploadStatus("Only admins or group admins can upload group-scoped documents.");
      return;
    }
    if (uploadScope === "public" && !canUploadPublic) {
      setUploadStatus("Only admins can upload public documents.");
      return;
    }
    setUploadStatus("Uploading...");
    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("user_email", currentUserEmail.trim());
    formData.append("scope", uploadScope);
    formData.append("group_id", uploadGroupId);
    formData.append("title", uploadTitle || uploadFile.name);
    formData.append("shared_with", uploadSharedWith);
    try {
      const res = await authedFetch(`${API_URL}/api/ingest/upload`, { method: "POST", body: formData });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Uploaded "${data.filename}" with ${data.scope} scope.`);
        setUploadFile(null);
        setUploadTitle("");
      } else {
        const err = await res.json();
        setUploadStatus(`Error: ${err.detail}`);
      }
    } catch (e) {
      setUploadStatus("Upload failed. Check the console.");
      console.error(e);
    }
  };

  const fetchClickupStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/oauth/clickup/status`);
      const data = await res.json();
      setClickupStatus(data);
    } catch (e) {
      console.error("Failed to fetch ClickUp status:", e);
    } finally {
      setConnectionsLoading(false);
    }
  };

  const connectClickUp = async () => {
    try {
      const res = await fetch(`${API_URL}/api/oauth/clickup/authorize`);
      const data = await res.json();
      window.location.href = data.url;
    } catch (e) {
      console.error("Failed to get ClickUp auth URL:", e);
    }
  };

  const disconnectClickUp = async () => {
    try {
      await fetch(`${API_URL}/api/oauth/clickup/disconnect`, { method: "DELETE" });
      fetchClickupStatus();
    } catch (e) {
      console.error("Failed to disconnect ClickUp:", e);
    }
  };

  const fetchGoogleStatus = async () => {
    if (!currentUserEmail) return;
    try {
      const res = await fetch(`${API_URL}/api/oauth/google/status?user_email=${encodeURIComponent(currentUserEmail)}`);
      const data = await res.json();
      setGoogleStatus(data);
    } catch (e) {
      console.error("Failed to fetch Google status:", e);
    }
  };

  const connectGoogle = async () => {
    if (!currentUserEmail) return;
    try {
      const res = await fetch(`${API_URL}/api/oauth/google/authorize?user_email=${encodeURIComponent(currentUserEmail)}`);
      const data = await res.json();
      window.location.href = data.url;
    } catch (e) {
      console.error("Failed to get Google auth URL:", e);
    }
  };

  const disconnectGoogle = async () => {
    if (!currentUserEmail) return;
    try {
      await fetch(`${API_URL}/api/oauth/google/disconnect?user_email=${encodeURIComponent(currentUserEmail)}`, { method: "DELETE" });
      fetchGoogleStatus();
    } catch (e) {
      console.error("Failed to disconnect Google:", e);
    }
  };

  const fetchSlackStatus = async () => {
    try {
      const url = currentUserEmail
        ? `${API_URL}/api/oauth/slack/status?user_email=${encodeURIComponent(currentUserEmail)}`
        : `${API_URL}/api/oauth/slack/status`;
      const res = await fetch(url);
      const data = await res.json();
      setSlackStatus(data);
    } catch (e) {
      console.error("Failed to fetch Slack status:", e);
    }
  };

  const connectSlack = async () => {
    if (!currentUserEmail) return;
    try {
      const res = await fetch(`${API_URL}/api/oauth/slack/authorize?user_email=${encodeURIComponent(currentUserEmail)}`);
      const data = await res.json();
      window.location.href = data.url;
    } catch (e) {
      console.error("Failed to get Slack auth URL:", e);
    }
  };

  const disconnectSlack = async () => {
    if (!currentUserEmail || disconnectingSlack) return;
    try {
      setDisconnectingSlack(true);
      await fetch(`${API_URL}/api/oauth/slack/disconnect?user_email=${encodeURIComponent(currentUserEmail)}`, { method: "DELETE" });
      fetchSlackStatus();
    } catch (e) {
      console.error("Failed to disconnect Slack:", e);
    } finally {
      setDisconnectingSlack(false);
    }
  };

  useEffect(() => {
    if (tab === "audit") fetchAuditLog();
    else if (tab === "review") fetchReviewQueue();
    else if (tab === "feedback") fetchFeedback();
    else if (tab === "metrics") fetchMetrics();
    else if (tab === "ingestion") {
      fetchSettings();
    } else if (tab === "users") fetchUsers();
    else if (tab === "groups") fetchGroups();
    else if (tab === "upload") fetchGroups();
    else if (tab === "no-index") fetchExclusionRules();
    else if (tab === "connections") {
      setConnectionsLoading(true);
      Promise.all([fetchClickupStatus(), fetchGoogleStatus(), fetchSlackStatus()]).finally(() =>
        setConnectionsLoading(false)
      );
    }
  }, [tab]);

  useEffect(() => {
    if (tab === "ingestion") fetchAvailableFolders();
  }, [tab, settings?.enabled_sources, currentUserEmail]);

  // Handle OAuth callback redirect params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("clickup") === "connected") {
      setTab("connections");
      fetchClickupStatus();
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("clickup") === "error") {
      setTab("connections");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("google") === "connected") {
      setTab("connections");
      fetchGoogleStatus();
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("google") === "error") {
      setTab("connections");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("slack") === "connected") {
      setTab("connections");
      fetchSlackStatus();
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("slack") === "error") {
      setTab("connections");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    fetchSelfRole();
  }, [currentUserEmail]);

  useEffect(() => {
    if (selfRole === "member") {
      router.replace("/");
    }
  }, [router, selfRole]);

  const handleReview = async (id: string, action: "approve" | "reject") => {
    try {
      const res = await fetch(
        `${API_URL}/api/admin/review-queue/${id}/${action}`,
        { method: "POST" }
      );
      if (res.ok) {
        setReviewQueue((prev) => prev.filter((item) => item.id !== id));
      }
    } catch (e) {
      console.error(`Failed to ${action}:`, e);
    }
  };

  const updateSettings = async (updates: Partial<IngestionSettings>) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        setSettings((prev) => (prev ? { ...prev, ...updates } : null));
      }
    } catch (e) {
      console.error("Failed to update settings:", e);
    }
  };

  const toggleSource = (source: string) => {
    if (!settings) return;
    const current = settings.enabled_sources || [];
    const next = current.includes(source)
      ? current.filter((s) => s !== source)
      : [...current, source];
    updateSettings({ enabled_sources: next });
  };

  const addFolder = (id: string) => {
    if (!settings || !id) return;
    const current = settings.google_drive_folder_ids || [];
    if (current.includes(id)) return;
    updateSettings({ google_drive_folder_ids: [...current, id] });
    setNewFolderId("");
  };

  const removeFolder = (id: string) => {
    if (!settings) return;
    const current = settings.google_drive_folder_ids || [];
    updateSettings({
      google_drive_folder_ids: current.filter((fid) => fid !== id),
    });
  };

  const triggerSync = async () => {
    if (!settings || syncing) return;
    const enabled = settings.enabled_sources || [];
    const payload: { source: string; folder_ids?: string[] } = { source: "all" };
    if (enabled.includes("drive") && settings.google_drive_folder_ids?.length) {
      payload.folder_ids = settings.google_drive_folder_ids;
    }

    try {
      setSyncing(true);
      const res = await fetch(`${API_URL}/api/ingest/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const detail = data?.detail || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      alert("Ingestion triggered for all enabled sources. Check backend logs for progress.");
    } catch (e) {
      console.error("Failed to trigger ingestion:", e);
      alert(`Failed to trigger ingestion: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setSyncing(false);
    }
  };

  const [adminOpen, setAdminOpen] = useState(false);

  const baseTabs = [
    { key: "connections", label: "Connections" },
    { key: "ingestion", label: "Sources" },
    { key: "upload", label: "Upload" },
    { key: "no-index", label: "No-Index Zones" },
  ] as const;
  const tabs = baseTabs.filter((t) => (t.key === "ingestion" ? canManageSources : true));

  useEffect(() => {
    if (tab === "ingestion" && !canManageSources) {
      setTab("upload");
    }
  }, [tab, canManageSources]);

  const adminTabs = [
    { key: "users", label: "Users" },
    { key: "groups", label: "Groups" },
    { key: "metrics", label: "Metrics" },
    { key: "audit", label: "Audit Log" },
    { key: "review", label: "Review Queue" },
    { key: "feedback", label: "Feedback" },
  ] as const;

  return (
    <main className="flex-1 overflow-y-auto h-full">
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#052e16]">Ingestion</h1>
        <div className="flex items-center gap-3">
          <div className="relative">
            <button
              onClick={() => setAdminOpen(!adminOpen)}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center gap-2 ${
                adminTabs.some(t => t.key === tab)
                  ? "bg-[#dcfce7] text-[#14532d] border-green-200"
                  : "bg-white/60 text-gray-600 border-gray-200 hover:bg-green-50 hover:text-green-800"
              }`}
            >
              ⚙ Admin
              <span className="text-xs opacity-60">▾</span>
            </button>
            {adminOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white/90 backdrop-blur-sm border border-green-100 rounded-xl shadow-lg shadow-green-900/5 py-1 z-50 min-w-[160px]">
                {adminTabs.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => { setTab(t.key); setAdminOpen(false); }}
                    className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                      tab === t.key
                        ? "bg-[#dcfce7] text-[#14532d] font-semibold"
                        : "text-gray-600 hover:bg-green-50 hover:text-green-800"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <a href="/" className="text-sm text-[#16a34a] hover:underline">
            &larr; Back to Oracle
          </a>
        </div>
      </div>

      <div className="flex gap-2 mb-6 flex-wrap">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setAdminOpen(false); }}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              tab === t.key
                ? "bg-[#dcfce7] text-[#14532d] border border-green-200 font-semibold"
                : "bg-white/60 text-gray-600 border border-gray-200 hover:bg-green-50 hover:text-green-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 p-4">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          Loading...
        </div>
      )}

      {/* Connections Tab */}
      {tab === "connections" && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-white mb-1">Integrations</h2>
            <p className="text-sm text-gray-400">Connect your tools so Xylem can ingest data and deliver alerts.</p>
          </div>

          {connectionsLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
              Checking connection status...
            </div>
          )}

          {/* ClickUp Card */}
          {!connectionsLoading && (
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-[#16a34a] rounded-lg flex items-center justify-center text-white font-bold text-sm">CU</div>
                  <div>
                    <h3 className="text-gray-900 font-semibold">ClickUp</h3>
                    <p className="text-xs text-gray-500">Ingest tasks, comments, and deliver Guardian alerts as ClickUp comments</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {clickupStatus?.connected ? (
                    <span className="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                      Connected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                      Not connected
                    </span>
                  )}
                </div>
              </div>

              {clickupStatus?.connected && (
                <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-gray-500 text-xs">Workspace</p>
                    <p className="text-gray-900 font-medium">{clickupStatus.workspace_name || "—"}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Team ID</p>
                    <p className="text-gray-900 font-medium">{clickupStatus.team_id || "—"}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Connected</p>
                    <p className="text-gray-900 font-medium">
                      {clickupStatus.connected_at
                        ? new Date(clickupStatus.connected_at).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" })
                        : "—"}
                    </p>
                  </div>
                </div>
              )}

              <div className="mt-4 flex gap-2">
                {clickupStatus?.connected ? (
                  <button
                    onClick={disconnectClickUp}
                    className="px-4 py-2 text-sm bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={connectClickUp}
                    className="px-4 py-2 text-sm bg-[#16a34a] text-white rounded-lg hover:bg-[#15803d] transition font-medium"
                  >
                    Connect ClickUp
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Google Card */}
          {!connectionsLoading && (
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white border border-gray-200 rounded-lg flex items-center justify-center text-sm font-bold">
                    <span style={{ background: "linear-gradient(135deg, #4285F4 25%, #EA4335 25%, #EA4335 50%, #FBBC05 50%, #FBBC05 75%, #34A853 75%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>G</span>
                  </div>
                  <div>
                    <h3 className="text-gray-900 font-semibold">Google</h3>
                    <p className="text-xs text-gray-500">Drive docs, Meet transcripts, Calendar events</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {googleStatus?.connected ? (
                    <span className="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                      Connected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                      Not connected
                    </span>
                  )}
                </div>
              </div>

              {googleStatus?.connected && (
                <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-gray-500 text-xs">Account</p>
                    <p className="text-gray-900 font-medium">{googleStatus.connected_email || "—"}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Connected</p>
                    <p className="text-gray-900 font-medium">
                      {googleStatus.connected_at
                        ? new Date(googleStatus.connected_at).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" })
                        : "—"}
                    </p>
                  </div>
                </div>
              )}

              <div className="mt-4 flex gap-2">
                {googleStatus?.connected ? (
                  // Anyone whose account is already connected can disconnect.
                  // (Edge case: a member whose role was downgraded after connecting
                  //  should still be able to revoke their own connection.)
                  <button
                    onClick={disconnectGoogle}
                    className="px-4 py-2 text-sm bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition"
                  >
                    Disconnect
                  </button>
                ) : me?.can_connect_sources ? (
                  <button
                    onClick={connectGoogle}
                    className="px-4 py-2 text-sm bg-[#16a34a] text-white rounded-lg hover:bg-[#15803d] transition font-medium"
                  >
                    Connect Google
                  </button>
                ) : (
                  <div className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 leading-relaxed">
                    🔒 Only admins and team leads can connect Google. Your meetings and files are private —
                    you can still query the Oracle and see decisions you have access to.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Slack Card */}
          <div className={`bg-white border rounded-xl p-6 ${slackStatus?.connected ? "border-[#16a34a]" : "border-gray-200"}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#16a34a] rounded-lg flex items-center justify-center text-white font-bold text-sm">S</div>
                <div>
                  <h3 className="text-gray-900 font-semibold">Slack</h3>
                  <p className="text-xs text-gray-500">Real-time message ingestion, slash commands, Guardian thread alerts</p>
                </div>
              </div>
              {slackStatus?.connected ? (
                <span className="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                  Connected
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                  Not connected
                </span>
              )}
            </div>
            {slackStatus?.connected ? (
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-gray-500 text-xs">Workspace</p>
                  <p className="text-gray-900 font-medium">{slackStatus.workspace_name || slackStatus.workspace_id || "—"}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Bot user</p>
                  <p className="text-gray-900 font-medium">{slackStatus.connected_by || "—"}</p>
                </div>
                {slackStatus.connected_at && (
                  <div>
                    <p className="text-gray-500 text-xs">Connected</p>
                    <p className="text-gray-900 font-medium">
                      {new Date(slackStatus.connected_at).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" })}
                    </p>
                  </div>
                )}
                <div className="col-span-2 mt-1">
                  <button
                    onClick={disconnectSlack}
                    disabled={disconnectingSlack}
                    className="px-4 py-2 text-sm bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {disconnectingSlack ? "Disconnecting..." : "Disconnect"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-3">
                  Connect your Slack workspace to enable message ingestion and real-time alerts.
                </p>
                <button
                  onClick={connectSlack}
                  disabled={!currentUserEmail}
                  className="px-4 py-2 bg-[#16a34a] hover:bg-[#15803d] text-white text-sm rounded-lg transition disabled:opacity-50"
                >
                  Connect Slack
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Metrics Tab */}
      {tab === "metrics" && !loading && metrics && (
        <div className="space-y-6">
          {/* Overview Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard
              label="Total Queries"
              value={metrics.overview.total_queries}
            />
            <StatCard label="Today" value={metrics.overview.queries_today} />
            <StatCard
              label="This Week"
              value={metrics.overview.queries_this_week}
            />
            <StatCard
              label="Unique Users"
              value={metrics.overview.unique_users}
            />
            <StatCard
              label="Avg Confidence"
              value={`${Math.round(metrics.overview.avg_confidence * 100)}%`}
            />
            <StatCard
              label="Avg Response"
              value={`${Math.round(metrics.overview.avg_response_time_ms / 1000)}s`}
            />
          </div>

          {/* PRD Success Metrics */}
          {(metrics.deflection || metrics.adherence) && (
            <div className="bg-white rounded-lg border p-5">
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="font-medium">PRD Success Metrics</h3>
                <span className="text-xs text-gray-400">last 30 days</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Deflection Rate */}
                {metrics.deflection && (
                  <div className="border rounded-lg p-4">
                    <div className="flex items-baseline justify-between mb-1">
                      <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Deflection Rate</span>
                      <span className="text-2xl font-black">{metrics.deflection.rate}%</span>
                    </div>
                    <p className="text-[11px] text-gray-500 mb-2">
                      Of incoming Slack/ClickUp content, {metrics.deflection.rate}% triggered a redundancy alert
                      (system caught prior context).
                    </p>
                    <div className="text-[11px] text-gray-400 font-mono">
                      {metrics.deflection.matches_found} matched / {metrics.deflection.checks_total} checks
                    </div>
                  </div>
                )}

                {/* Decision Adherence */}
                {metrics.adherence && (
                  <div className="border rounded-lg p-4">
                    <div className="flex items-baseline justify-between mb-1">
                      <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Decision Adherence</span>
                      <span className="text-2xl font-black">{metrics.adherence.rate}%</span>
                    </div>
                    <p className="text-[11px] text-gray-500 mb-2">
                      {metrics.adherence.active_decisions} of {metrics.adherence.total_decisions} decisions still active.
                      Higher = team sticks to recorded decisions.
                    </p>
                    <div className="text-[11px] text-gray-400 font-mono">
                      {metrics.adherence.reversed_last_30d} reversed in 30d
                    </div>
                  </div>
                )}

                {/* Retrieval Time vs PRD target */}
                <div className="border rounded-lg p-4">
                  <div className="flex items-baseline justify-between mb-1">
                    <span className="text-xs uppercase tracking-wider text-gray-500 font-bold">Retrieval Time</span>
                    <span className="text-2xl font-black">
                      {(metrics.overview.avg_response_time_ms / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500 mb-2">
                    PRD target: under 30s (vs. 15min of manual digging).
                    {metrics.overview.avg_response_time_ms < 30000 ? " Hitting target." : " Above target."}
                  </p>
                  <div className="text-[11px] text-gray-400 font-mono">
                    avg across {metrics.overview.total_queries} queries
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Feedback Summary */}
          <div className="bg-white rounded-lg border p-5">
            <h3 className="font-medium mb-3">Answer Quality (User Feedback)</h3>
            {metrics.feedback.total > 0 ? (
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 rounded-full bg-green-500"
                    style={{
                      width: `${Math.max(metrics.feedback.helpfulness_rate * 2, 20)}px`,
                    }}
                  ></div>
                  <span className="text-sm">
                    {metrics.feedback.helpful} helpful (
                    {metrics.feedback.helpfulness_rate}%)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 rounded-full bg-red-400"
                    style={{
                      width: `${Math.max((100 - metrics.feedback.helpfulness_rate) * 2, 20)}px`,
                    }}
                  ></div>
                  <span className="text-sm">
                    {metrics.feedback.not_helpful} not helpful
                  </span>
                </div>
                <span className="text-sm text-gray-500">
                  ({metrics.feedback.total} total ratings)
                </span>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                No feedback collected yet.
              </p>
            )}
          </div>

          {/* Agent & Query Type Usage */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Agent Usage</h3>
              {Object.keys(metrics.agent_usage).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(metrics.agent_usage).map(([agent, count]) => (
                    <div key={agent} className="flex justify-between text-sm">
                      <span className="capitalize">{agent}</span>
                      <span className="font-mono text-gray-600">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No agent data yet (new metrics start tracking from now).
                </p>
              )}
            </div>
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Query Types</h3>
              {Object.keys(metrics.query_type_usage).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(metrics.query_type_usage).map(
                    ([qtype, count]) => (
                      <div
                        key={qtype}
                        className="flex justify-between text-sm"
                      >
                        <span>{qtype}</span>
                        <span className="font-mono text-gray-600">{count}</span>
                      </div>
                    )
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No query type data yet.
                </p>
              )}
            </div>
          </div>

          {/* Daily Usage */}
          {metrics.daily_usage.length > 0 && (
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Daily Queries (Last 7 Days)</h3>
              <div className="flex items-end gap-2 h-32">
                {metrics.daily_usage.map((d) => {
                  const maxCount = Math.max(
                    ...metrics.daily_usage.map((x) => x.count)
                  );
                  const height = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
                  return (
                    <div
                      key={d.date}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <span className="text-xs text-gray-600">{d.count}</span>
                      <div
                        className="w-full bg-blue-500 rounded-t"
                        style={{ height: `${Math.max(height, 4)}%` }}
                      ></div>
                      <span className="text-xs text-gray-400">
                        {d.date.slice(5)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Audit Log Tab */}
      {tab === "audit" && !loading && (
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  User
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Question
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Results
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {auditLog.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {entry.timestamp
                      ? new Date(entry.timestamp).toLocaleString()
                      : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-sm">{entry.user_email}</td>
                  <td className="px-4 py-3 text-sm max-w-md truncate">
                    {entry.query}
                  </td>
                  <td className="px-4 py-3 text-sm">{entry.result_count}</td>
                </tr>
              ))}
              {auditLog.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No audit log entries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Review Queue Tab */}
      {tab === "review" && !loading && (
        <div className="grid gap-4">
          {reviewQueue.map((item) => (
            <div key={item.id} className="p-5 bg-white rounded-lg border">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full mr-2">
                    {item.decision_type}
                  </span>
                  <span className="text-sm text-gray-500">
                    Confidence: {Math.round(item.confidence * 100)}%
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString()
                    : ""}
                </span>
              </div>

              <h3 className="font-medium mb-1">{item.proposed_decision}</h3>
              <p className="text-sm text-gray-600 mb-1">
                <span className="font-medium">Rationale:</span>{" "}
                {item.proposed_rationale}
              </p>
              {item.trigger_phrase && (
                <p className="text-xs text-gray-500 mb-3">
                  Trigger: &ldquo;{item.trigger_phrase}&rdquo;
                </p>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => handleReview(item.id, "approve")}
                  className="px-4 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReview(item.id, "reject")}
                  className="px-4 py-1.5 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
                >
                  Reject
                </button>
                {item.source_url && (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-1.5 text-sm text-blue-600 hover:underline"
                  >
                    View source
                  </a>
                )}
              </div>
            </div>
          ))}
          {reviewQueue.length === 0 && (
            <div className="p-8 text-center text-gray-500 bg-white rounded-lg border">
              No pending items in the review queue.
            </div>
          )}
        </div>
      )}

      {/* Feedback Tab */}
      {tab === "feedback" && !loading && (
        <div className="space-y-3">
          {feedbackList.map((f) => (
            <div
              key={f.id}
              className="p-4 bg-white rounded-lg border flex items-start gap-4"
            >
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                  f.rating === "helpful"
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {f.rating === "helpful" ? "Helpful" : "Not Helpful"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{f.query}</p>
                {f.comment && (
                  <p className="text-xs text-gray-500 mt-1">{f.comment}</p>
                )}
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  <span>{f.agent}</span>
                  <span>{f.query_type}</span>
                  <span>{Math.round(f.confidence * 100)}% confidence</span>
                  <span>
                    {f.created_at
                      ? new Date(f.created_at).toLocaleString()
                      : ""}
                  </span>
                </div>
              </div>
            </div>
          ))}
          {feedbackList.length === 0 && (
            <div className="p-8 text-center text-gray-500 bg-white rounded-lg border">
              No feedback collected yet. Users can rate answers in the chat.
            </div>
          )}
        </div>
      )}

      {/* Ingestion Tab */}
      {tab === "ingestion" && canManageSources && !loading && settings && (
        <div className="space-y-8">
          {/* Sources Section */}
          <section className="bg-white rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 text-gray-800">
              Ingestion Sources
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { id: "drive", label: "Google Drive" },
                { id: "calendar", label: "Google Calendar" },
                { id: "meet", label: "Meet Transcripts" },
                { id: "slack", label: "Slack" },
                { id: "clickup", label: "ClickUp" },
              ].map((source) => (
                <div
                  key={source.id}
                  className="flex items-center justify-between p-4 rounded-lg border bg-gray-50 bg-opacity-50"
                >
                  <span className="font-medium text-gray-700">
                    {source.label}
                  </span>
                  <button
                    onClick={() => toggleSource(source.id)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                        settings.enabled_sources?.includes(source.id)
                        ? "bg-blue-600"
                        : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        settings.enabled_sources?.includes(source.id)
                          ? "translate-x-6"
                          : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* Google Drive Configuration */}
          <section className="bg-white rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 text-gray-800">
              Google Drive Configuration
            </h2>
            <div className="space-y-6">
              {/* Active folders */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-3">
                  Active Folders
                </label>
                <div className="flex flex-wrap gap-2 mb-1">
                  {(settings.google_drive_folder_ids || []).map((id) => {
                    const folder = availableFolders.find((f) => f.id === id);
                    return (
                      <div
                        key={id}
                        className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full border border-blue-100 text-sm"
                      >
                        <span className="font-medium">{folder?.name || id}</span>
                        <button
                          onClick={() => removeFolder(id)}
                          className="text-blue-400 hover:text-red-500 transition-colors leading-none"
                        >
                          &times;
                        </button>
                      </div>
                    );
                  })}
                  {(settings.google_drive_folder_ids || []).length === 0 && (
                    <div className="flex items-start gap-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-xs w-full">
                      <span>⚠️</span>
                      <span>No folders selected — entire Drive will be scanned. Select specific folders below to restrict ingestion.</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Search & add by name */}
              <div className="pt-4 border-t">
                <label className="block text-sm font-medium text-gray-500 mb-3">
                  Search Folders by Name
                </label>
                <input
                  type="text"
                  value={folderSearch}
                  onChange={(e) => setFolderSearch(e.target.value)}
                  placeholder="Type a folder name to filter..."
                  className="w-full px-4 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm mb-3"
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-60 overflow-y-auto">
                  {availableFolders
                    .filter((f) =>
                      folderSearch.trim() === "" || f.name.toLowerCase().includes(folderSearch.toLowerCase())
                    )
                    .map((folder) => {
                      const already = settings.google_drive_folder_ids?.includes(folder.id);
                      return (
                        <button
                          key={folder.id}
                          onClick={() => { addFolder(folder.id); setFolderSearch(""); }}
                          disabled={already}
                          className={`text-left p-3 rounded-lg border text-sm transition-all shadow-sm ${
                            already
                              ? "bg-gray-700/40 text-gray-500 border-gray-600 cursor-default"
                              : "border-gray-600 hover:border-blue-400 hover:bg-blue-500/10 text-gray-200"
                          }`}
                        >
                          <div className="font-medium truncate">📁 {folder.name}</div>
                          <div className="text-xs font-mono text-gray-500 truncate mt-0.5">{folder.id}</div>
                          {already && <div className="text-xs text-green-400 mt-0.5">✓ Added</div>}
                        </button>
                      );
                    })}
                  {availableFolders.filter((f) =>
                    folderSearch.trim() === "" || f.name.toLowerCase().includes(folderSearch.toLowerCase())
                  ).length === 0 && (
                    <p className="text-sm text-gray-400 col-span-3">No folders match &ldquo;{folderSearch}&rdquo;</p>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Action Footer */}
          <div className="flex justify-start pt-4">
            <button
                onClick={triggerSync}
                disabled={syncing}
                className="px-6 py-3 bg-gray-800 text-white rounded-xl text-sm font-medium hover:bg-black transition-colors shadow-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {syncing ? "Syncing..." : "Trigger Sync Now"}
            </button>
          </div>
        </div>
      )}

      {/* ── Users Tab ─────────────────────────────────────────── */}
      {tab === "users" && !loading && (
        <div className="space-y-6">
          {/* Add User */}
          <section className="bg-white rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4">Add User</h2>
            {!canManageUsers && (
              <p className="text-sm text-gray-500 mb-3">
                Admin role required to add/remove users or change roles.
              </p>
            )}
            <div className="flex gap-3 flex-wrap">
              <input
                type="email"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                placeholder="user@company.com"
                disabled={!canManageUsers}
                className={`flex-1 min-w-48 px-4 py-2 rounded-lg border text-sm outline-none ${
                  canManageUsers
                    ? "focus:ring-2 focus:ring-blue-500"
                    : "bg-gray-100 text-gray-400 cursor-not-allowed"
                }`}
              />
              <select
                value={newUserRole}
                onChange={(e) => setNewUserRole(e.target.value)}
                disabled={!canManageUsers}
                className={`px-4 py-2 rounded-lg border text-sm outline-none ${
                  canManageUsers
                    ? "focus:ring-2 focus:ring-blue-500"
                    : "bg-gray-100 text-gray-400 cursor-not-allowed"
                }`}
              >
                <option value="member">Member</option>
                <option value="group_admin">Group Admin</option>
                <option value="admin">Admin</option>
              </select>
              <button
                onClick={createUser}
                disabled={!canManageUsers}
                className={`px-5 py-2 rounded-lg text-sm font-medium ${
                  canManageUsers
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-gray-200 text-gray-500 cursor-not-allowed"
                }`}
              >
                Add User
              </button>
            </div>
          </section>

          {/* User List */}
          <section className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Display Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-mono">{u.email}</td>
                    <td className="px-4 py-3 text-sm">{u.display_name || "—"}</td>
                    <td className="px-4 py-3 text-sm">
                      <RoleBadge role={u.role} />
                    </td>
                    <td className="px-4 py-3 text-sm flex gap-2">
                      <select
                        value={u.role}
                        onChange={(e) => updateUserRole(u.email, e.target.value)}
                        disabled={!canManageUsers}
                        className={`text-xs px-2 py-1 rounded border ${
                          canManageUsers
                            ? ""
                            : "bg-gray-100 text-gray-400 cursor-not-allowed"
                        }`}
                      >
                        <option value="member">member</option>
                        <option value="group_admin">group_admin</option>
                        <option value="admin">admin</option>
                      </select>
                      <button
                        onClick={() => deleteUser(u.email)}
                        disabled={!canManageUsers}
                        className={`text-xs px-2 py-1 rounded border ${
                          canManageUsers
                            ? "border-red-200 text-red-600 hover:bg-red-50"
                            : "border-gray-200 text-gray-400 cursor-not-allowed"
                        }`}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-500">No users yet. Add the first one above.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        </div>
      )}

      {/* ── Groups Tab ────────────────────────────────────────── */}
      {tab === "groups" && !loading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Group List */}
          <div className="space-y-4">
            {/* Create Group */}
            <section className="bg-white rounded-xl border p-5">
              <h2 className="text-base font-semibold mb-3">Create Group</h2>
              <div className="space-y-2">
                <input
                  type="text"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  placeholder="Group name (e.g. Engineering)"
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
                <input
                  type="text"
                  value={newGroupDesc}
                  onChange={(e) => setNewGroupDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
                <button
                  onClick={createGroup}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
                >
                  Create Group
                </button>
              </div>
            </section>

            {/* List */}
            {groups.map((g) => (
              <div
                key={g.id}
                onClick={() => fetchGroupDetail(g.id)}
                className={`p-4 bg-white rounded-xl border cursor-pointer hover:border-blue-400 transition-colors ${selectedGroup?.id === g.id ? "border-blue-500 ring-2 ring-blue-200" : ""}`}
              >
                <div className="font-medium text-sm">{g.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">{g.description || "No description"}</div>
                <div className="text-xs text-gray-400 mt-1">{g.member_count} member{g.member_count !== 1 ? "s" : ""}</div>
              </div>
            ))}
            {groups.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">No groups yet.</p>
            )}
          </div>

          {/* Group Detail */}
          <div className="md:col-span-2">
            {selectedGroup ? (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedGroup.name}</h2>
                    <p className="text-sm text-gray-500">{selectedGroup.description}</p>
                  </div>
                  <button
                    onClick={() => deleteGroup(selectedGroup.id)}
                    className="text-xs px-3 py-1.5 border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
                  >
                    Delete Group
                  </button>
                </div>

                {/* Add Member */}
                <div>
                  <h3 className="text-sm font-medium mb-2">Add Member</h3>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={addMemberEmail}
                      onChange={(e) => setAddMemberEmail(e.target.value)}
                      placeholder="user@company.com"
                      className="flex-1 px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                    <select
                      value={addMemberRole}
                      onChange={(e) => setAddMemberRole(e.target.value)}
                      className="px-3 py-2 rounded-lg border text-sm"
                    >
                      <option value="member">Member</option>
                      <option value="group_admin">Group Admin</option>
                    </select>
                    <button
                      onClick={() => addMember(selectedGroup.id)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
                    >
                      Add
                    </button>
                  </div>
                </div>

                {/* Member List */}
                <div>
                  <h3 className="text-sm font-medium mb-2">Members ({selectedGroup.members?.length ?? 0})</h3>
                  <div className="space-y-2">
                    {(selectedGroup.members || []).map((m) => (
                      <div key={m.user_email} className="flex items-center justify-between p-2 rounded-lg bg-gray-50">
                        <div>
                          <span className="text-sm font-mono">{m.user_email}</span>
                          <RoleBadge role={m.role} className="ml-2" />
                        </div>
                        <button
                          onClick={() => removeMember(selectedGroup.id, m.user_email)}
                          className="text-xs px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {(!selectedGroup.members || selectedGroup.members.length === 0) && (
                      <p className="text-sm text-gray-400">No members yet.</p>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-medium mb-2">Group Documents ({groupDocuments.length})</h3>
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {groupDocuments.map((d) => (
                      <div key={d.id} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-medium truncate">{d.title}</div>
                            <div className="text-xs text-gray-500 mt-0.5">
                              {d.source} • {d.doc_status}
                            </div>
                          </div>
                          {d.url ? (
                            <a
                              href={d.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50"
                            >
                              Open
                            </a>
                          ) : (
                            <span className="text-xs text-gray-400">No link</span>
                          )}
                          <button
                            onClick={() => selectedGroup && deleteGroupDocument(selectedGroup.id, d.id)}
                            disabled={!canManageSelectedGroup}
                            className={`text-xs px-2 py-1 rounded border ${
                              canManageSelectedGroup
                                ? "border-red-200 text-red-600 hover:bg-red-50"
                                : "border-gray-200 text-gray-400 cursor-not-allowed"
                            }`}
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                    {groupDocuments.length === 0 && (
                      <p className="text-sm text-gray-400">No group-scoped documents found yet.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
                Select a group to manage its members.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Upload Tab ────────────────────────────────────────── */}
      {/* ── No-Index Zones Tab ──────────────────────────────── */}
      {tab === "no-index" && !loading && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold">No-Index Zones</h2>
            <p className="text-sm text-gray-400 mt-1">
              Exclude specific Slack channels, Drive folders, or ClickUp spaces from ingestion. Content in these zones will never be indexed.
            </p>
          </div>

          {/* Add new rule */}
          <div className="bg-white rounded-xl border p-5 space-y-4">
            <h3 className="font-medium text-sm">Add Exclusion Rule</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Source</label>
                <select
                  value={newRuleSource}
                  onChange={(e) => setNewRuleSource(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="slack">Slack Channel</option>
                  <option value="drive">Drive Folder</option>
                  <option value="clickup">ClickUp Space</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {newRuleSource === "slack" ? "Channel ID" : newRuleSource === "drive" ? "Folder ID" : "Space ID"}
                </label>
                <input
                  type="text"
                  value={newRuleIdentifier}
                  onChange={(e) => setNewRuleIdentifier(e.target.value)}
                  placeholder={newRuleSource === "slack" ? "C0123ABCDEF" : "folder-or-space-id"}
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Display Name</label>
                <input
                  type="text"
                  value={newRuleName}
                  onChange={(e) => setNewRuleName(e.target.value)}
                  placeholder="#hr-private, Salary Docs, etc."
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Reason (optional)</label>
                <input
                  type="text"
                  value={newRuleReason}
                  onChange={(e) => setNewRuleReason(e.target.value)}
                  placeholder="Sensitive HR content"
                  className="w-full px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>
            <button
              onClick={createExclusionRule}
              disabled={!newRuleIdentifier.trim()}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-40 transition-colors"
            >
              Add No-Index Rule
            </button>
          </div>

          {/* Existing rules */}
          {exclusionRules.length === 0 ? (
            <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
              No exclusion rules configured. All sources are being indexed.
            </div>
          ) : (
            <div className="bg-white rounded-xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                  <tr>
                    <th className="px-4 py-3 text-left">Source</th>
                    <th className="px-4 py-3 text-left">Name</th>
                    <th className="px-4 py-3 text-left">Identifier</th>
                    <th className="px-4 py-3 text-left">Reason</th>
                    <th className="px-4 py-3 text-left">Created</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {exclusionRules.map((rule) => (
                    <tr key={rule.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          rule.source_type === "slack" ? "bg-teal-100 text-teal-700" :
                          rule.source_type === "drive" ? "bg-blue-100 text-blue-700" :
                          "bg-green-100 text-green-700"
                        }`}>
                          {rule.source_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-medium">{rule.name || "—"}</td>
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">{rule.identifier}</td>
                      <td className="px-4 py-3 text-gray-500">{rule.reason || "—"}</td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{rule.created_at ? new Date(rule.created_at).toLocaleDateString() : ""}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => deleteExclusionRule(rule.id)}
                          className="text-red-500 hover:text-red-700 text-xs font-medium"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "upload" && (
        <div className="max-w-2xl space-y-6">
          <section className="bg-white rounded-xl border p-6 space-y-5">
            <h2 className="text-lg font-semibold">Upload Document</h2>
            <p className="text-sm text-gray-500">
              Upload a document to the knowledge base. Choose the visibility scope — public documents are available company-wide.
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Signed-in User</label>
              <input
                type="email"
                value={currentUserEmail}
                readOnly
                className="w-full px-4 py-2 rounded-lg border text-sm bg-gray-100 text-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Visibility Scope</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: "private", label: "Private", desc: "Only you" },
                  { value: "group", label: "Group", desc: "Your team" },
                  { value: "public", label: "Public", desc: "Everyone (admin only)" },
                ].map((s) => {
                  const disabled =
                    (s.value === "group" && !canUploadGroup) ||
                    (s.value === "public" && !canUploadPublic);
                  return (
                    <button
                      key={s.value}
                      onClick={() => !disabled && setUploadScope(s.value)}
                      disabled={disabled}
                      className={`p-3 rounded-lg border text-left transition-colors ${
                        uploadScope === s.value
                          ? "border-blue-500 bg-blue-50"
                          : disabled
                            ? "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed"
                            : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <div className="text-sm font-medium">{s.label}</div>
                      <div className="text-xs text-gray-500">{s.desc}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {uploadScope === "group" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Select Group</label>
                <select
                  value={uploadGroupId}
                  onChange={(e) => setUploadGroupId(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="">— Select a group —</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
            )}

            {uploadScope === "private" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Share with (optional, comma-separated emails)
                </label>
                <input
                  type="text"
                  value={uploadSharedWith}
                  onChange={(e) => setUploadSharedWith(e.target.value)}
                  placeholder="colleague@company.com, another@company.com"
                  className="w-full px-4 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Document Title (optional)</label>
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="Leave blank to use filename"
                className="w-full px-4 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
              <input
                type="file"
                accept=".txt,.md,.pdf,.doc,.docx"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>

            <button
              onClick={handleUpload}
              className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
            >
              Upload Document
            </button>

            {uploadStatus && (
              <p className={`text-sm text-center ${uploadStatus.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>
                {uploadStatus}
              </p>
            )}
          </section>
        </div>
      )}
    </div>
    </main>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="bg-white rounded-lg border p-4 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function RoleBadge({ role, className = "" }: { role: string; className?: string }) {
  const colors: Record<string, string> = {
    admin: "bg-red-100 text-red-700",
    group_admin: "bg-orange-100 text-orange-700",
    member: "bg-gray-100 text-gray-600",
  };
  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[role] ?? "bg-gray-100 text-gray-600"} ${className}`}
    >
      {role}
    </span>
  );
}
