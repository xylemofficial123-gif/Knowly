"use client";

import { useMemo, useState } from "react";

interface EntityNode {
  id: string;
  canonical_name: string;
  entity_type: string;
  mention_count: number;
  source_count: number;
}

interface EntityLink {
  source: string;
  target: string;
  weight: number;
}

interface Props {
  entities: EntityNode[];
  links?: EntityLink[];
}

const TYPE_META: Record<string, { label: string; color: string; bg: string }> = {
  project: { label: "Projects", color: "#9333ea", bg: "#faf5ff" },
  person:  { label: "People",   color: "#2563eb", bg: "#eff6ff" },
  feature: { label: "Features", color: "#ec4899", bg: "#fdf2f8" },
  tool:    { label: "Tools",    color: "#d97706", bg: "#fffbeb" },
  acronym: { label: "Acronyms", color: "#10b981", bg: "#ecfdf5" },
  other:   { label: "Other",    color: "#6b7280", bg: "#f9fafb" },
};

const TYPE_ORDER = ["project", "person", "feature", "tool", "acronym", "other"];

// Canvas — generous margins so pills never clip.
// H is sized so center + RING_2_RADIUS + pill height fits within H with a buffer.
const W = 1400;
const H = 1240;
const CX = W / 2;
const CY = H / 2;

const HUB_RADIUS = 200;        // distance from root to hub
const RING_1_RADIUS = 360;     // first ring of entity pills
const RING_2_RADIUS = 510;     // second ring (only if category has >4 entities)
const MAX_PER_CATEGORY = 8;

const PILL_HEIGHT = 30;
const PILL_PADDING_X = 14;
const FONT_PX = 12;
const AVG_CHAR_PX = 6.5;
const MAX_LABEL_CHARS = 22;

interface PositionedEntity extends EntityNode {
  x: number;
  y: number;
  pillW: number;
  display: string;
  ring: number;
}

interface PositionedCategory {
  type: string;
  meta: typeof TYPE_META[string];
  hubX: number;
  hubY: number;
  entities: PositionedEntity[];
  hidden: number;
  hubAngle: number;
}

function truncate(s: string, n = MAX_LABEL_CHARS): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function pillWidth(text: string): number {
  return Math.ceil(text.length * AVG_CHAR_PX + PILL_PADDING_X * 2);
}

function layout(entities: EntityNode[]): PositionedCategory[] {
  // Bucket by type and order canonically
  const byType = new Map<string, EntityNode[]>();
  for (const e of entities) {
    const t = TYPE_META[e.entity_type] ? e.entity_type : "other";
    if (!byType.has(t)) byType.set(t, []);
    byType.get(t)!.push(e);
  }
  const cats: { type: string; entities: EntityNode[] }[] = [];
  for (const t of TYPE_ORDER) {
    const list = byType.get(t);
    if (list && list.length > 0) {
      list.sort((a, b) => b.mention_count - a.mention_count);
      cats.push({ type: t, entities: list });
    }
  }
  const n = cats.length;
  if (n === 0) return [];

  const sectorAngle = (2 * Math.PI) / n;

  return cats.map((cat, idx) => {
    // Sector centers start at top (-PI/2), evenly spaced clockwise
    const hubAngle = -Math.PI / 2 + idx * sectorAngle;
    const meta = TYPE_META[cat.type] || TYPE_META.other;

    const hubX = CX + Math.cos(hubAngle) * HUB_RADIUS;
    const hubY = CY + Math.sin(hubAngle) * HUB_RADIUS;

    // Cap visible entities; tally hidden remainder
    const visible = cat.entities.slice(0, MAX_PER_CATEGORY);
    const hidden = cat.entities.length - visible.length;

    // Two-ring layout: split visible roughly in half between inner and outer ring
    const ring1Count = Math.min(visible.length, 4);
    const ring2Count = Math.max(0, visible.length - 4);

    const positioned: PositionedEntity[] = [];
    const placeRing = (count: number, ringIdx: number, ringRadius: number) => {
      if (count === 0) return;
      // Available angular spread for this ring within the sector
      const spread = sectorAngle * 0.82;
      for (let i = 0; i < count; i++) {
        const t = count === 1 ? 0.5 : i / (count - 1);
        const angle = hubAngle - spread / 2 + t * spread;
        const x = CX + Math.cos(angle) * ringRadius;
        const y = CY + Math.sin(angle) * ringRadius;
        const sourceIdx = ringIdx === 0 ? i : 4 + i;
        const e = visible[sourceIdx];
        const display = truncate(e.canonical_name);
        positioned.push({
          ...e,
          x,
          y,
          pillW: pillWidth(display),
          display,
          ring: ringIdx,
        });
      }
    };
    placeRing(ring1Count, 0, RING_1_RADIUS);
    placeRing(ring2Count, 1, RING_2_RADIUS);

    return {
      type: cat.type,
      meta,
      hubX,
      hubY,
      entities: positioned,
      hidden,
      hubAngle,
    };
  });
}

function curve(x1: number, y1: number, x2: number, y2: number, bend = 0.18): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy);
  if (len === 0) return `M${x1} ${y1}`;
  const nx = -dy / len;
  const ny = dx / len;
  return `M${x1} ${y1} Q${mx + nx * len * bend} ${my + ny * len * bend} ${x2} ${y2}`;
}

export default function EntityGraphView({ entities }: Props) {
  const [hovered, setHovered] = useState<PositionedEntity | null>(null);
  const categories = useMemo(() => layout(entities), [entities]);

  if (entities.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
        <p className="text-sm text-gray-400">No entities yet — ingest documents to populate the graph.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden relative">
      {/* Hover detail card */}
      {hovered && (
        <div className="absolute top-4 right-4 z-10 bg-white rounded-xl border border-gray-100 px-4 py-3 shadow-md max-w-xs pointer-events-none">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: TYPE_META[hovered.entity_type]?.color || TYPE_META.other.color }}
            />
            <span className="font-black text-foreground text-sm">{hovered.canonical_name}</span>
          </div>
          <div className="text-[11px] text-gray-500">
            {hovered.mention_count} mention{hovered.mention_count === 1 ? "" : "s"} · {hovered.source_count} source{hovered.source_count === 1 ? "" : "s"}
          </div>
        </div>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full block"
        style={{ height: "auto", maxHeight: 760 }}
      >
        <defs>
          {/* Soft drop shadow for floating elements */}
          <filter id="soft-shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="3" />
            <feOffset dx="0" dy="2" result="offsetblur" />
            <feComponentTransfer>
              <feFuncA type="linear" slope="0.12" />
            </feComponentTransfer>
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Subtle radial background */}
          <radialGradient id="bg-gradient" cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="#fafafa" />
            <stop offset="100%" stopColor="#f3f4f6" />
          </radialGradient>
        </defs>

        {/* Background */}
        <rect x="0" y="0" width={W} height={H} fill="url(#bg-gradient)" />

        {/* Subtle ring guides */}
        <circle cx={CX} cy={CY} r={HUB_RADIUS} fill="none" stroke="rgba(0,0,0,0.04)" strokeDasharray="3 6" />
        <circle cx={CX} cy={CY} r={RING_1_RADIUS} fill="none" stroke="rgba(0,0,0,0.03)" strokeDasharray="3 6" />

        {/* Root → Hub trunks (drawn first so they sit beneath everything) */}
        {categories.map((cat) => (
          <path
            key={`trunk-${cat.type}`}
            d={curve(CX, CY, cat.hubX, cat.hubY, 0)}
            stroke={cat.meta.color}
            strokeWidth={2.5}
            strokeLinecap="round"
            fill="none"
            opacity={0.45}
          />
        ))}

        {/* Hub → Entity branches */}
        {categories.map((cat) =>
          cat.entities.map((e) => (
            <path
              key={`branch-${e.id}`}
              d={curve(cat.hubX, cat.hubY, e.x, e.y, 0.12)}
              stroke={cat.meta.color}
              strokeWidth={1.2}
              fill="none"
              opacity={0.3}
            />
          ))
        )}

        {/* Entity pills */}
        {categories.map((cat) =>
          cat.entities.map((e) => {
            const isHovered = hovered?.id === e.id;
            const dotR = Math.max(3, Math.min(7, 2 + Math.sqrt(e.mention_count)));
            return (
              <g
                key={e.id}
                transform={`translate(${e.x - e.pillW / 2}, ${e.y - PILL_HEIGHT / 2})`}
                onMouseEnter={() => setHovered(e)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}
                filter="url(#soft-shadow)"
              >
                <rect
                  width={e.pillW}
                  height={PILL_HEIGHT}
                  rx={PILL_HEIGHT / 2}
                  ry={PILL_HEIGHT / 2}
                  fill={isHovered ? cat.meta.color : "white"}
                  stroke={cat.meta.color}
                  strokeWidth={isHovered ? 0 : 1.5}
                />
                {/* Mention-count dot */}
                <circle
                  cx={PILL_PADDING_X - 2}
                  cy={PILL_HEIGHT / 2}
                  r={dotR}
                  fill={isHovered ? "white" : cat.meta.color}
                  opacity={isHovered ? 1 : 0.8}
                />
                <text
                  x={PILL_PADDING_X + dotR + 6}
                  y={PILL_HEIGHT / 2}
                  dominantBaseline="middle"
                  fontSize={FONT_PX}
                  fontFamily="Inter, system-ui, sans-serif"
                  fontWeight={isHovered ? 700 : 600}
                  fill={isHovered ? "white" : "#1f2937"}
                  style={{ pointerEvents: "none" }}
                >
                  {e.display}
                </text>
              </g>
            );
          })
        )}

        {/* Category hubs (drawn after branches so they sit on top) */}
        {categories.map((cat) => {
          const hubW = 130;
          const hubH = 48;
          const hidden = cat.hidden;
          return (
            <g key={`hub-${cat.type}`} filter="url(#soft-shadow)">
              <rect
                x={cat.hubX - hubW / 2}
                y={cat.hubY - hubH / 2}
                width={hubW}
                height={hubH}
                rx={hubH / 2}
                ry={hubH / 2}
                fill={cat.meta.color}
                stroke="white"
                strokeWidth={2.5}
              />
              <text
                x={cat.hubX}
                y={cat.hubY - 6}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={13}
                fontWeight={800}
                fontFamily="Inter, system-ui, sans-serif"
                fill="white"
                style={{ pointerEvents: "none", letterSpacing: "0.5px" }}
              >
                {cat.meta.label.toUpperCase()}
              </text>
              <text
                x={cat.hubX}
                y={cat.hubY + 10}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={10}
                fontFamily="Inter, system-ui, sans-serif"
                fill="rgba(255,255,255,0.85)"
                style={{ pointerEvents: "none" }}
              >
                {cat.entities.length + hidden} {(cat.entities.length + hidden) === 1 ? "entity" : "entities"}
                {hidden > 0 ? ` · +${hidden} hidden` : ""}
              </text>
            </g>
          );
        })}

        {/* Root */}
        <g filter="url(#soft-shadow)">
          <rect
            x={CX - 70}
            y={CY - 26}
            width={140}
            height={52}
            rx={26}
            ry={26}
            fill="#1f2937"
          />
          <text
            x={CX}
            y={CY}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={14}
            fontWeight={800}
            fontFamily="Inter, system-ui, sans-serif"
            fill="white"
            style={{ pointerEvents: "none", letterSpacing: "1px" }}
          >
            KNOWLEDGE
          </text>
        </g>
      </svg>
    </div>
  );
}
