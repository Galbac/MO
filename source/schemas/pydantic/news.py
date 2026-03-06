from pydantic import BaseModel, Field


class NewsCategoryItem(BaseModel):
    id: int
    slug: str
    name: str


class TagItem(BaseModel):
    id: int
    slug: str
    name: str


class NewsArticleSummary(BaseModel):
    id: int
    slug: str
    title: str
    subtitle: str | None = None
    lead: str | None = None
    cover_image_url: str | None = None
    status: str
    published_at: str | None = None
    category: NewsCategoryItem | None = None
    tags: list[TagItem] = Field(default_factory=list)


class NewsArticleDetail(NewsArticleSummary):
    content_html: str
    seo_title: str | None = None
    seo_description: str | None = None
    related_news: list["NewsArticleSummary"] = Field(default_factory=list)


class NewsArticleCreateRequest(BaseModel):
    slug: str
    title: str
    subtitle: str | None = None
    lead: str | None = None
    content_html: str
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    seo_title: str | None = None
    seo_description: str | None = None
    status: str = "draft"


class NewsStatusRequest(BaseModel):
    status: str
    publish_at: str | None = None


NewsArticleDetail.model_rebuild()
