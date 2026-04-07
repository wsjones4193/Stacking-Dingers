/**
 * Admin page — four sections:
 *   /admin/player-mapping  → confirm/edit player ID mappings
 *   /admin/score-audit     → view score discrepancies
 *   /admin/articles        → create/edit/delete articles
 *   /admin/podcasts        → sync + delete podcast episodes
 */
import { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { AlertCircle, Check, Plus, Trash2, X } from "lucide-react";
import {
  adminCreateArticle,
  adminCreateEpisode,
  adminDeleteArticle,
  adminDeleteEpisode,
  adminListArticles,
  adminUpdateArticle,
  confirmMapping,
  getPlayerMappings,
  getPodcasts,
  getScoreAudit,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { PlayerMapping, PodcastEpisode, ScoreAuditEntry } from "@/types/api";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Image } from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";

const SEASONS = [2026, 2025, 2024, 2023, 2022];

// ---------------------------------------------------------------------------
// Player Mapping
// ---------------------------------------------------------------------------

function PlayerMappingPage() {
  const [mappings, setMappings] = useState<PlayerMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"unconfirmed" | "all">("unconfirmed");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editMlbId, setEditMlbId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getPlayerMappings({ confirmed: filter === "unconfirmed" ? false : undefined })
      .then(setMappings)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  async function handleConfirm(id: number) {
    const mlbId = parseInt(editMlbId, 10);
    if (isNaN(mlbId)) return;
    setSaving(true);
    try {
      const updated = await confirmMapping(id, mlbId);
      setMappings((prev) => prev.map((m) => (m.id === id ? updated : m)));
      setEditingId(null);
      setEditMlbId("");
    } catch (e) {
      alert(`Failed to confirm: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Player Mappings</h2>
          <p className="text-sm text-muted-foreground">
            Link Underdog player names to MLB Stats API IDs.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={filter === "unconfirmed" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("unconfirmed")}
          >
            Unconfirmed
          </Button>
          <Button
            variant={filter === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("all")}
          >
            All
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Underdog Name</th>
                  <th className="pb-2">MLB Name</th>
                  <th className="pb-2">MLB ID</th>
                  <th className="pb-2">Season</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((m) => (
                  <tr key={m.id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{m.underdog_name}</td>
                    <td className="py-1.5 text-muted-foreground">{m.mlb_name ?? "—"}</td>
                    <td className="py-1.5 text-muted-foreground">
                      {editingId === m.id ? (
                        <Input
                          value={editMlbId}
                          onChange={(e) => setEditMlbId(e.target.value)}
                          className="h-7 w-28 text-xs"
                          placeholder="MLB API ID"
                          autoFocus
                        />
                      ) : (
                        m.mlb_id ?? "—"
                      )}
                    </td>
                    <td className="py-1.5">{m.season}</td>
                    <td className="py-1.5">
                      {m.confirmed ? (
                        <Badge variant="default" className="text-xs">Confirmed</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-400/40">Pending</Badge>
                      )}
                    </td>
                    <td className="py-1.5">
                      {editingId === m.id ? (
                        <div className="flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-primary"
                            onClick={() => handleConfirm(m.id)}
                            disabled={saving}
                          >
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-muted-foreground"
                            onClick={() => { setEditingId(null); setEditMlbId(""); }}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : !m.confirmed ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          onClick={() => {
                            setEditingId(m.id);
                            setEditMlbId(m.mlb_id != null ? String(m.mlb_id) : "");
                          }}
                        >
                          Edit
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {mappings.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No mappings found.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score Audit
// ---------------------------------------------------------------------------

function ScoreAuditPage() {
  const [entries, setEntries] = useState<ScoreAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [season, setSeason] = useState(2026);

  useEffect(() => {
    setLoading(true);
    getScoreAudit(season)
      .then(setEntries)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season]);

  const sorted = [...entries].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Score Audit</h2>
          <p className="text-sm text-muted-foreground">
            Discrepancies between calculated scores and Underdog's official scores (|delta| ≥ 0.5).
          </p>
        </div>
        <div className="flex gap-1">
          {SEASONS.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={season === s ? "default" : "outline"}
              onClick={() => setSeason(s)}
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Player</th>
                  <th className="pb-2 text-right">Week</th>
                  <th className="pb-2 text-right">Calculated</th>
                  <th className="pb-2 text-right">Underdog</th>
                  <th className="pb-2 text-right">Delta</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((e) => (
                  <tr key={e.id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{e.player_name ?? `ID ${e.player_id}`}</td>
                    <td className="py-1.5 text-right">Wk {e.week_number}</td>
                    <td className="py-1.5 text-right">{e.calculated_score.toFixed(2)}</td>
                    <td className="py-1.5 text-right">{e.underdog_score.toFixed(2)}</td>
                    <td className={`py-1.5 text-right font-medium ${e.delta > 0 ? "text-primary" : "text-destructive"}`}>
                      {e.delta > 0 ? "+" : ""}{e.delta.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sorted.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No discrepancies found for {season}.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Articles admin
// ---------------------------------------------------------------------------

type ArticleRow = {
  article_id: number;
  title: string;
  author: string;
  published_date: string;
  slug: string;
  updated_at: string;
};

type ArticleFormData = {
  title: string;
  author: string;
  published_date: string;
  excerpt: string;
  thumbnail_url: string;
  slug: string;
};

const EMPTY_FORM: ArticleFormData = {
  title: "",
  author: "",
  published_date: new Date().toISOString().slice(0, 10),
  excerpt: "",
  thumbnail_url: "",
  slug: "",
};

function slugify(str: string) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function ArticleEditor({
  initialHtml,
  onChange,
}: {
  initialHtml: string;
  onChange: (html: string) => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Image,
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: initialHtml,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  // Toolbar helper
  const btn = (label: string, action: () => void, active?: boolean) => (
    <button
      type="button"
      onMouseDown={(e) => { e.preventDefault(); action(); }}
      className={`px-2 py-0.5 rounded text-xs border ${active ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"}`}
    >
      {label}
    </button>
  );

  if (!editor) return null;

  const addImage = () => {
    const url = window.prompt("Image URL");
    if (url) editor.chain().focus().setImage({ src: url }).run();
  };

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-1 p-2 border-b border-border bg-muted/40">
        {btn("B", () => editor.chain().focus().toggleBold().run(), editor.isActive("bold"))}
        {btn("I", () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"))}
        {btn("H2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
        {btn("H3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
        {btn("UL", () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList"))}
        {btn("OL", () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList"))}
        {btn("—", () => editor.chain().focus().setHorizontalRule().run())}
        {btn("Img", addImage)}
        {btn("Table", () =>
          editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        )}
      </div>
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none p-3 min-h-[200px] focus-within:outline-none"
      />
    </div>
  );
}

function ArticlesAdminPage() {
  const [articles, setArticles] = useState<ArticleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ArticleRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<ArticleFormData>(EMPTY_FORM);
  const [contentHtml, setContentHtml] = useState("");
  const [editHtml, setEditHtml] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    adminListArticles()
      .then(setArticles)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setContentHtml("");
    setCreating(true);
    setEditing(null);
  }

  function openEdit(a: ArticleRow) {
    setForm({
      title: a.title,
      author: a.author,
      published_date: a.published_date.slice(0, 10),
      excerpt: "",
      thumbnail_url: "",
      slug: a.slug,
    });
    setEditHtml("");
    setEditing(a);
    setCreating(false);
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (creating) {
        await adminCreateArticle({
          ...form,
          content_html: contentHtml,
          thumbnail_url: form.thumbnail_url || undefined,
        });
      } else if (editing) {
        const patch: Record<string, string> = {};
        if (form.title) patch.title = form.title;
        if (form.author) patch.author = form.author;
        if (form.published_date) patch.published_date = form.published_date;
        if (form.excerpt) patch.excerpt = form.excerpt;
        if (form.thumbnail_url) patch.thumbnail_url = form.thumbnail_url;
        if (form.slug) patch.slug = form.slug;
        if (editHtml) patch.content_html = editHtml;
        await adminUpdateArticle(editing.article_id, patch);
      }
      closeForm();
      load();
    } catch (e) {
      alert(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this article?")) return;
    try {
      await adminDeleteArticle(id);
      setArticles((prev) => prev.filter((a) => a.article_id !== id));
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  }

  const showForm = creating || editing !== null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Articles</h2>
          <p className="text-sm text-muted-foreground">Create and manage written content.</p>
        </div>
        {!showForm && (
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-3.5 w-3.5 mr-1" /> New Article
          </Button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {showForm && (
        <Card>
          <CardContent className="pt-4 space-y-3">
            <h3 className="font-semibold text-sm">{creating ? "New Article" : "Edit Article"}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Title</label>
                <Input
                  value={form.title}
                  onChange={(e) => {
                    const t = e.target.value;
                    setForm((f) => ({ ...f, title: t, slug: creating ? slugify(t) : f.slug }));
                  }}
                  placeholder="Article title"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Author</label>
                <Input
                  value={form.author}
                  onChange={(e) => setForm((f) => ({ ...f, author: e.target.value }))}
                  placeholder="Author name"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Published Date</label>
                <Input
                  type="date"
                  value={form.published_date}
                  onChange={(e) => setForm((f) => ({ ...f, published_date: e.target.value }))}
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Excerpt</label>
                <Input
                  value={form.excerpt}
                  onChange={(e) => setForm((f) => ({ ...f, excerpt: e.target.value }))}
                  placeholder="Short description for card view"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Slug</label>
                <Input
                  value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                  placeholder="url-friendly-slug"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Thumbnail URL (optional)</label>
                <Input
                  value={form.thumbnail_url}
                  onChange={(e) => setForm((f) => ({ ...f, thumbnail_url: e.target.value }))}
                  placeholder="https://..."
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Content {editing && "(leave unchanged to keep existing content)"}
              </label>
              <ArticleEditor
                initialHtml={editing ? "" : ""}
                onChange={creating ? setContentHtml : setEditHtml}
              />
            </div>
            <div className="flex gap-2 pt-1">
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
              <Button size="sm" variant="outline" onClick={closeForm}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Title</th>
                  <th className="pb-2">Author</th>
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Slug</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {articles.map((a) => (
                  <tr key={a.article_id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{a.title}</td>
                    <td className="py-1.5 text-muted-foreground">{a.author}</td>
                    <td className="py-1.5 text-muted-foreground">
                      {new Date(a.published_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </td>
                    <td className="py-1.5 text-xs text-muted-foreground font-mono">{a.slug}</td>
                    <td className="py-1.5">
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => openEdit(a)}>
                          Edit
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(a.article_id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {articles.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No articles yet.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Podcasts admin
// ---------------------------------------------------------------------------

type EpisodeForm = {
  youtube_url: string;
  title: string;
  published_date: string;
  series: string;
  description: string;
};

const EMPTY_EPISODE_FORM: EpisodeForm = {
  youtube_url: "",
  title: "",
  published_date: new Date().toISOString().slice(0, 10),
  series: "",
  description: "",
};

function PodcastsAdminPage() {
  const [episodes, setEpisodes] = useState<PodcastEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<EpisodeForm>(EMPTY_EPISODE_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getPodcasts(1)
      .then((res) => setEpisodes(res.episodes))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAdd() {
    if (!form.youtube_url.trim() || !form.title.trim() || !form.published_date) {
      alert("YouTube URL, title, and date are required.");
      return;
    }
    setSaving(true);
    try {
      await adminCreateEpisode({
        youtube_url: form.youtube_url.trim(),
        title: form.title.trim(),
        published_date: form.published_date,
        series: form.series.trim() || undefined,
        description: form.description.trim(),
      });
      setForm(EMPTY_EPISODE_FORM);
      setShowForm(false);
      load();
    } catch (e) {
      alert(`Failed to add episode: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remove this episode?")) return;
    try {
      await adminDeleteEpisode(id);
      setEpisodes((prev) => prev.filter((ep) => ep.episode_id !== id));
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Podcasts</h2>
          <p className="text-sm text-muted-foreground">Manually add YouTube episodes.</p>
        </div>
        {!showForm && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="h-3.5 w-3.5 mr-1" /> Add Episode
          </Button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {showForm && (
        <Card>
          <CardContent className="pt-4 space-y-3">
            <h3 className="font-semibold text-sm">Add Episode</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">YouTube URL or Video ID <span className="text-destructive">*</span></label>
                <Input
                  value={form.youtube_url}
                  onChange={(e) => setForm((f) => ({ ...f, youtube_url: e.target.value }))}
                  placeholder="https://www.youtube.com/watch?v=... or video ID"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Title <span className="text-destructive">*</span></label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Episode title"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Published Date <span className="text-destructive">*</span></label>
                <Input
                  type="date"
                  value={form.published_date}
                  onChange={(e) => setForm((f) => ({ ...f, published_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Series</label>
                <Input
                  value={form.series}
                  onChange={(e) => setForm((f) => ({ ...f, series: e.target.value }))}
                  placeholder="e.g. Draft Season 2026"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Description (optional)</label>
                <Input
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Short description"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <Button size="sm" onClick={handleAdd} disabled={saving}>
                {saving ? "Saving…" : "Add Episode"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setShowForm(false); setForm(EMPTY_EPISODE_FORM); }}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Title</th>
                  <th className="pb-2">Series</th>
                  <th className="pb-2">Date</th>
                  <th className="pb-2">YouTube ID</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {episodes.map((ep) => (
                  <tr key={ep.episode_id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{ep.title}</td>
                    <td className="py-1.5 text-muted-foreground">{ep.series ?? "—"}</td>
                    <td className="py-1.5 text-muted-foreground">
                      {new Date(ep.published_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </td>
                    <td className="py-1.5 font-mono text-xs text-muted-foreground">{ep.youtube_id}</td>
                    <td className="py-1.5">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(ep.episode_id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {episodes.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No episodes yet. Click "Add Episode" to get started.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin layout
// ---------------------------------------------------------------------------

function AdminNav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
      isActive ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
    }`;

  return (
    <div className="mb-6 flex items-center gap-3 border-b border-border pb-3">
      <h1 className="text-xl font-bold mr-4">Admin</h1>
      <NavLink to="/admin/player-mapping" className={linkClass}>Player Mapping</NavLink>
      <NavLink to="/admin/score-audit" className={linkClass}>Score Audit</NavLink>
      <NavLink to="/admin/articles" className={linkClass}>Articles</NavLink>
      <NavLink to="/admin/podcasts" className={linkClass}>Podcasts</NavLink>
    </div>
  );
}

export default function Admin() {
  return (
    <div>
      <AdminNav />
      <Routes>
        <Route path="player-mapping" element={<PlayerMappingPage />} />
        <Route path="score-audit" element={<ScoreAuditPage />} />
        <Route path="articles" element={<ArticlesAdminPage />} />
        <Route path="podcasts" element={<PodcastsAdminPage />} />
        <Route index element={<PlayerMappingPage />} />
      </Routes>
    </div>
  );
}
