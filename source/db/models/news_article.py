from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class NewsArticle(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "news_articles"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead: Mapped[str | None] = mapped_column(Text(), nullable=True)
    content_html: Mapped[str] = mapped_column(Text())
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("news_categories.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
