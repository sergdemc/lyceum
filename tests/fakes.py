from lyceum.domain.protocols import FetchedPage, OutboundPost, PublishReceipt

FIXED_SUMMARY = "Коротко: в материале разбирают, как не упереться в лишние запросы к базе."


class FakeFetcher:
    def __init__(self) -> None:
        self.pages: dict[str, FetchedPage] = {}
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        return self.pages[url]


class FakeSummarizer:
    def __init__(self, summary: str = FIXED_SUMMARY) -> None:
        self.summary = summary
        self.calls: list[str] = []
        self.on_summarize = None

    def summarize(self, text: str, *, title: str | None = None) -> str:
        del title
        self.calls.append(text)
        if self.on_summarize is not None:
            self.on_summarize()
        return self.summary


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[OutboundPost] = []

    def publish(self, post: OutboundPost) -> PublishReceipt:
        self.messages.append(post)
        message_id = 500 + len(self.messages)
        chat_id = int(post.telegram_chat_id)
        tail = str(chat_id)
        if tail.startswith("-100"):
            tail = tail[4:]
        return PublishReceipt(
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
            url=f"https://t.me/c/{tail}/{message_id}",
        )
