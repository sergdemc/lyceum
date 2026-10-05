from enum import StrEnum


class ArticleSource(StrEnum):
    URL = 'url'
    RAW_TEXT = 'raw_text'
    READY_POST = 'ready_post'


class ArticleStatus(StrEnum):
    RECEIVED = 'received'
    EXTRACTED = 'extracted'
    AWAITING_REVIEW = 'awaiting_review'
    REJECTED = 'rejected'
    PUBLISHED = 'published'
    # Имена серии. Переходов в этом срезе нет.
    APPROVED = 'approved'
    SCHEDULED = 'scheduled'
