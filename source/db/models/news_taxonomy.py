from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin


class NewsCategory(Base, IdIntPkMixin):
    __tablename__ = "news_categories"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)


class Tag(Base, IdIntPkMixin):
    __tablename__ = "tags"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
