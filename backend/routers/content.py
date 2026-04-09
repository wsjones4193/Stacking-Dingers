"""
/api/content/* — public read endpoints for articles and podcast episodes.

GET /api/content/articles              — paginated article list (no content_html)
GET /api/content/articles/{slug}       — full article including content_html
GET /api/content/podcasts              — paginated episode list, newest first
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.db.models import Article, PodcastEpisode

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

class ArticleSummary(BaseModel):
    article_id: int
    title: str
    author: str
    published_date: str
    excerpt: str
    thumbnail_url: str | None
    slug: str
    category: str | None


class ArticleDetail(BaseModel):
    article_id: int
    title: str
    author: str
    published_date: str
    excerpt: str
    thumbnail_url: str | None
    slug: str
    category: str | None
    content_html: str
    updated_at: str


class ArticleListResponse(BaseModel):
    articles: list[ArticleSummary]
    total: int
    page: int
    page_size: int


class EpisodeSummary(BaseModel):
    episode_id: int
    youtube_id: str
    title: str
    published_date: str
    description: str
    thumbnail_url: str | None
    series: str | None


class EpisodeListResponse(BaseModel):
    episodes: list[EpisodeSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# GET /api/content/articles
# ---------------------------------------------------------------------------

@router.get("/articles", response_model=ArticleListResponse)
def list_articles(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
):
    """Paginated article list, newest first. Does not include content_html."""
    stmt = select(Article).order_by(Article.published_date.desc())
    all_articles = session.exec(stmt).all()
    total = len(all_articles)
    start = (page - 1) * page_size
    page_articles = all_articles[start : start + page_size]

    return ArticleListResponse(
        articles=[
            ArticleSummary(
                article_id=a.article_id,
                title=a.title,
                author=a.author,
                published_date=a.published_date.isoformat(),
                excerpt=a.excerpt,
                thumbnail_url=a.thumbnail_url,
                slug=a.slug,
                category=a.category,
            )
            for a in page_articles
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /api/content/articles/{slug}
# ---------------------------------------------------------------------------

@router.get("/articles/{slug}", response_model=ArticleDetail)
def get_article(slug: str, session: SessionDep):
    """Full article detail including content_html."""
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return ArticleDetail(
        article_id=article.article_id,
        title=article.title,
        author=article.author,
        published_date=article.published_date.isoformat(),
        excerpt=article.excerpt,
        thumbnail_url=article.thumbnail_url,
        slug=article.slug,
        category=article.category,
        content_html=article.content_html,
        updated_at=article.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/content/podcasts
# ---------------------------------------------------------------------------

@router.get("/podcasts", response_model=EpisodeListResponse)
def list_podcasts(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
):
    """Paginated podcast episode list, newest first."""
    stmt = select(PodcastEpisode).order_by(PodcastEpisode.published_date.desc())
    all_episodes = session.exec(stmt).all()
    total = len(all_episodes)
    start = (page - 1) * page_size
    page_episodes = all_episodes[start : start + page_size]

    return EpisodeListResponse(
        episodes=[
            EpisodeSummary(
                episode_id=e.episode_id,
                youtube_id=e.youtube_id,
                title=e.title,
                published_date=e.published_date.isoformat(),
                description=e.description,
                thumbnail_url=e.thumbnail_url,
                series=e.series,
            )
            for e in page_episodes
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
