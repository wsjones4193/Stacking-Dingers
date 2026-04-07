/**
 * Podcasts page — grid of YouTube episodes from the @StackingDingers channel.
 * Route: /podcasts
 */
import { useEffect, useState } from "react";
import { Mic } from "lucide-react";
import { getPodcasts } from "@/lib/api";
import type { PodcastEpisode } from "@/types/api";
import LoadingSpinner from "@/components/LoadingSpinner";

// Placeholder links — replace with real URLs once confirmed
const APPLE_PODCASTS_URL = "https://podcasts.apple.com";
const SPOTIFY_URL = "https://open.spotify.com";

const PAGE_SIZE = 12;

function EpisodeCard({ episode }: { episode: PodcastEpisode }) {
  const watchUrl = `https://www.youtube.com/watch?v=${episode.youtube_id}`;

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-card">
      {/* Embedded YouTube player */}
      <div className="relative w-full" style={{ paddingBottom: "56.25%" }}>
        <iframe
          src={`https://www.youtube.com/embed/${episode.youtube_id}`}
          title={episode.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 h-full w-full"
          loading="lazy"
        />
      </div>

      <div className="flex flex-1 flex-col p-4">
        {episode.series && (
          <span className="mb-2 inline-block self-start rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {episode.series}
          </span>
        )}
        <a
          href={watchUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-sm leading-snug hover:text-primary transition-colors mb-2"
        >
          {episode.title}
        </a>
        <p className="text-xs text-muted-foreground mb-2">
          {new Date(episode.published_date).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
        {episode.description && (
          <p className="text-xs text-muted-foreground line-clamp-3">
            {episode.description}
          </p>
        )}
      </div>
    </div>
  );
}

export default function Podcasts() {
  const [episodes, setEpisodes] = useState<PodcastEpisode[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getPodcasts(page)
      .then((res) => {
        setEpisodes(res.episodes);
        setTotal(res.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Podcasts</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Episodes from the Stacking Dingers YouTube channel.
        </p>
      </div>

      {/* Platform links banner */}
      <div className="mb-6 flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
        <Mic className="h-4 w-4 text-primary shrink-0" />
        <span className="text-sm text-muted-foreground">Also available on:</span>
        <a
          href={APPLE_PODCASTS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-primary hover:underline"
        >
          Apple Podcasts
        </a>
        <span className="text-muted-foreground">·</span>
        <a
          href={SPOTIFY_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-primary hover:underline"
        >
          Spotify
        </a>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {!loading && !error && (
        <>
          {episodes.length === 0 ? (
            <p className="text-muted-foreground text-sm">No episodes available yet.</p>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {episodes.map((ep) => (
                  <EpisodeCard key={ep.episode_id} episode={ep} />
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
        </>
      )}
    </div>
  );
}
