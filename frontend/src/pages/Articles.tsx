/**
 * Articles page — list view and detail view for admin-authored written content.
 * Route: /articles (list) and /articles/:slug (detail).
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Calendar, User } from "lucide-react";
import { getArticles, getArticle } from "@/lib/api";
import type { ArticleSummary, ArticleDetail } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import LoadingSpinner from "@/components/LoadingSpinner";

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
          <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
            {article.excerpt}
          </p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {article.author}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(article.published_date).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
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
  const PAGE_SIZE = 12;

  useEffect(() => {
    setLoading(true);
    getArticles(page)
      .then((res) => {
        setArticles(res.articles);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Articles</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Strategy, analysis, and research from the Stacking Dingers team.
        </p>
      </div>

      {articles.length === 0 ? (
        <p className="text-muted-foreground text-sm">No articles published yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {articles.map((a) => (
              <ArticleCard key={a.article_id} article={a} />
            ))}
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
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
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
    getArticle(slug)
      .then(setArticle)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!article) return null;

  return (
    <div className="max-w-3xl mx-auto">
      <Link
        to="/articles"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All articles
      </Link>

      {article.thumbnail_url && (
        <img
          src={article.thumbnail_url}
          alt={article.title}
          className="w-full rounded-lg object-cover max-h-72 mb-6"
        />
      )}

      <h1 className="text-3xl font-bold leading-tight mb-3">{article.title}</h1>

      <div className="flex items-center gap-4 text-sm text-muted-foreground mb-8 pb-6 border-b border-border">
        <span className="flex items-center gap-1">
          <User className="h-3.5 w-3.5" />
          {article.author}
        </span>
        <span className="flex items-center gap-1">
          <Calendar className="h-3.5 w-3.5" />
          {new Date(article.published_date).toLocaleDateString("en-US", {
            month: "long",
            day: "numeric",
            year: "numeric",
          })}
        </span>
      </div>

      {/* Rich-text content — content_html is admin-authored, not user input */}
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
// Page component — switches between list and detail based on slug param
// ---------------------------------------------------------------------------

export default function Articles() {
  const { slug } = useParams<{ slug?: string }>();
  return slug ? <ArticleDetailView slug={slug} /> : <ArticleList />;
}
