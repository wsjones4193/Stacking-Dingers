/**
 * Articles page — public list/detail view with a floating admin button
 * for creating articles behind a simple password gate.
 * Routes: /articles (list) and /articles/:slug (detail).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Calendar, Plus, User, X } from "lucide-react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Image } from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { getArticles, getArticle, adminCreateArticle } from "@/lib/api";
import type { ArticleSummary, ArticleDetail } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import LoadingSpinner from "@/components/LoadingSpinner";

const ADMIN_PASSWORD = "DingersStacked";

function slugify(str: string) {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// ---------------------------------------------------------------------------
// Rich text editor
// ---------------------------------------------------------------------------

function ArticleEditor({ onChange }: { onChange: (html: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Image,
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: "",
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  const btn = (label: string, action: () => void, active?: boolean) => (
    <button
      key={label}
      type="button"
      onMouseDown={(e) => { e.preventDefault(); action(); }}
      className={`px-2 py-0.5 rounded text-xs border ${active ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"}`}
    >
      {label}
    </button>
  );

  if (!editor) return null;

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <div className="flex flex-wrap gap-1 p-2 border-b border-border bg-muted/40">
        {btn("B", () => editor.chain().focus().toggleBold().run(), editor.isActive("bold"))}
        {btn("I", () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"))}
        {btn("H2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
        {btn("H3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
        {btn("UL", () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList"))}
        {btn("OL", () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList"))}
        {btn("—", () => editor.chain().focus().setHorizontalRule().run())}
        {btn("Img", () => {
          const url = window.prompt("Image URL");
          if (url) editor.chain().focus().setImage({ src: url }).run();
        })}
      </div>
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none p-3 min-h-[240px] focus-within:outline-none"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Password gate modal
// ---------------------------------------------------------------------------

function PasswordModal({ onSuccess, onClose }: { onSuccess: () => void; onClose: () => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (value === ADMIN_PASSWORD) {
      onSuccess();
    } else {
      setError(true);
      setValue("");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base">Enter password</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            ref={inputRef}
            type="password"
            placeholder="Password"
            value={value}
            onChange={(e) => { setValue(e.target.value); setError(false); }}
            className={error ? "border-destructive" : ""}
          />
          {error && <p className="text-xs text-destructive">Incorrect password.</p>}
          <Button type="submit" className="w-full">Continue</Button>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Article editor modal
// ---------------------------------------------------------------------------

type ArticleForm = {
  title: string;
  author: string;
  published_date: string;
  excerpt: string;
  thumbnail_url: string;
  slug: string;
};

const EMPTY_FORM: ArticleForm = {
  title: "",
  author: "",
  published_date: new Date().toISOString().slice(0, 10),
  excerpt: "",
  thumbnail_url: "",
  slug: "",
};

function ArticleEditorModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<ArticleForm>(EMPTY_FORM);
  const [contentHtml, setContentHtml] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!form.title.trim() || !form.author.trim()) {
      alert("Title and author are required.");
      return;
    }
    setSaving(true);
    try {
      await adminCreateArticle({
        title: form.title,
        author: form.author,
        published_date: form.published_date,
        excerpt: form.excerpt,
        content_html: contentHtml,
        thumbnail_url: form.thumbnail_url || undefined,
        slug: form.slug || slugify(form.title),
      });
      onSaved();
      onClose();
    } catch (e) {
      alert(`Failed to save: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 overflow-y-auto py-8 px-4">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-base">New Article</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form */}
        <div className="p-6 space-y-4">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Title <span className="text-destructive">*</span></label>
            <Input
              value={form.title}
              onChange={(e) => {
                const t = e.target.value;
                setForm((f) => ({ ...f, title: t, slug: slugify(t) }));
              }}
              placeholder="Article title"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Author <span className="text-destructive">*</span></label>
              <Input
                value={form.author}
                onChange={(e) => setForm((f) => ({ ...f, author: e.target.value }))}
                placeholder="Your name"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Date</label>
              <Input
                type="date"
                value={form.published_date}
                onChange={(e) => setForm((f) => ({ ...f, published_date: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-muted-foreground block mb-1">Excerpt <span className="text-xs font-normal">(shown on article card)</span></label>
            <Input
              value={form.excerpt}
              onChange={(e) => setForm((f) => ({ ...f, excerpt: e.target.value }))}
              placeholder="One or two sentence summary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Thumbnail URL <span className="text-xs font-normal">(optional)</span></label>
              <Input
                value={form.thumbnail_url}
                onChange={(e) => setForm((f) => ({ ...f, thumbnail_url: e.target.value }))}
                placeholder="https://..."
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Slug</label>
              <Input
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                placeholder="auto-generated from title"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-muted-foreground block mb-1">Content</label>
            <ArticleEditor onChange={setContentHtml} />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Publishing…" : "Publish Article"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Article list view
// ---------------------------------------------------------------------------

function ArticleCard({ article }: { article: ArticleSummary }) {
  return (
    <Link to={`/articles/${article.slug}`} className="group block">
      <Card className="overflow-hidden transition-shadow hover:shadow-md h-full">
        {article.thumbnail_url && (
          <img
            src={article.thumbnail_url}
            alt={article.title}
            className="w-full h-44 object-cover"
          />
        )}
        <CardContent className="p-4">
          <h2 className="font-semibold text-base leading-snug group-hover:text-primary transition-colors mb-2">
            {article.title}
          </h2>
          <p className="text-sm text-muted-foreground line-clamp-3 mb-3">{article.excerpt}</p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {article.author}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(article.published_date).toLocaleDateString("en-US", {
                month: "short", day: "numeric", year: "numeric",
              })}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function ArticleList() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const PAGE_SIZE = 12;

  const load = useCallback(() => {
    setLoading(true);
    getArticles(page)
      .then((res) => { setArticles(res.articles); setTotal(res.total); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="relative">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Articles</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Strategy, analysis, and research from the Stacking Dingers team.
        </p>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {!loading && !error && (
        <>
          {articles.length === 0 ? (
            <p className="text-muted-foreground text-sm">No articles published yet.</p>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {articles.map((a) => <ArticleCard key={a.article_id} article={a} />)}
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 mt-8">
                  <button
                    className="text-sm px-3 py-1.5 rounded border border-border hover:bg-accent disabled:opacity-40"
                    onClick={() => setPage((p) => p - 1)}
                    disabled={page === 1}
                  >
                    Previous
                  </button>
                  <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
                  <button
                    className="text-sm px-3 py-1.5 rounded border border-border hover:bg-accent disabled:opacity-40"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page === totalPages}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Floating add button */}
      <button
        onClick={() => setShowPassword(true)}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
        aria-label="New article"
      >
        <Plus className="h-5 w-5" />
      </button>

      {showPassword && (
        <PasswordModal
          onSuccess={() => { setShowPassword(false); setShowEditor(true); }}
          onClose={() => setShowPassword(false)}
        />
      )}

      {showEditor && (
        <ArticleEditorModal
          onClose={() => setShowEditor(false)}
          onSaved={load}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Article detail view
// ---------------------------------------------------------------------------

function ArticleDetailView({ slug }: { slug: string }) {
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getArticle(slug).then(setArticle).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
  }, [slug]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!article) return null;

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/articles" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="h-3.5 w-3.5" />
        All articles
      </Link>

      {article.thumbnail_url && (
        <img src={article.thumbnail_url} alt={article.title} className="w-full rounded-lg object-cover max-h-72 mb-6" />
      )}

      <h1 className="text-3xl font-bold leading-tight mb-3">{article.title}</h1>

      <div className="flex items-center gap-4 text-sm text-muted-foreground mb-8 pb-6 border-b border-border">
        <span className="flex items-center gap-1"><User className="h-3.5 w-3.5" />{article.author}</span>
        <span className="flex items-center gap-1">
          <Calendar className="h-3.5 w-3.5" />
          {new Date(article.published_date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </span>
      </div>

      <div
        className="prose prose-sm max-w-none text-foreground
          prose-headings:text-foreground prose-headings:font-semibold
          prose-a:text-primary prose-a:no-underline hover:prose-a:underline
          prose-strong:text-foreground
          prose-table:border prose-td:border prose-td:border-border prose-th:border prose-th:border-border
          prose-img:rounded-md"
        dangerouslySetInnerHTML={{ __html: article.content_html }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export default function Articles() {
  const { slug } = useParams<{ slug?: string }>();
  return slug ? <ArticleDetailView slug={slug} /> : <ArticleList />;
}
