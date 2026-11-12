"""Reddit discussion collection through an Apify actor.

Reddit is used for anecdotal community signals (layoff chatter, entry-level
difficulty, salary talk), never as authoritative evidence. This adapter is
interchangeable with any other ``WebSearchCrawler``: replacing Apify with the
official Reddit API later only requires a new class with ``search_documents``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import SearchQuery, WebDocument


DEFAULT_ACTOR = "harshmaur/reddit-scraper"
COMMUNITY_TIER = "community_discussion"
COMMENTS_PER_DOCUMENT = 5


class ApifyRedditClient:
    """Search Reddit posts (with top comments) via Apify's run-sync API."""

    def __init__(
        self,
        api_token: str | None = None,
        *,
        actor_id: str | None = None,
        base_url: str = "https://api.apify.com/v2",
        timeout_seconds: int = 300,
        comments_per_post: int = 5,
        time_filter: str = "year",
    ) -> None:
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            raise ValueError("Set APIFY_API_TOKEN before using the Reddit collector")
        self.actor_id = actor_id or os.getenv("APIFY_REDDIT_ACTOR") or DEFAULT_ACTOR
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.comments_per_post = comments_per_post
        self.time_filter = time_filter

    def search_documents(
        self,
        query: SearchQuery,
        limit: int,
    ) -> list[WebDocument]:
        searches = list(query.variants or (query.text,))
        items = self._run_actor(self._actor_input(searches, limit))
        return reddit_documents(items, query, limit * len(searches))

    def _actor_input(self, searches: list[str], limit: int) -> dict[str, Any]:
        """Each Apify actor has its own input schema; map ours onto it."""

        if self.actor_id.startswith("trudax/"):
            return {
                "searches": searches,
                "searchPosts": True,
                "searchComments": False,
                "searchCommunities": False,
                "searchUsers": False,
                "sort": "relevance",
                "time": self.time_filter,
                "includeNSFW": False,
                "includeMediaLinks": True,
                "maxPostCount": limit,
                "maxComments": self.comments_per_post,
                # Posts plus their comments; bounds the pay-per-result cost.
                "maxItems": limit * len(searches) * (self.comments_per_post + 1),
                "proxy": {"useApifyProxy": True},
            }
        return {
            "searchTerms": searches,
            "searchPosts": True,
            "searchComments": False,
            "searchCommunities": False,
            "searchSort": "relevance",
            "searchTime": self.time_filter,
            "includeNSFW": False,
            "crawlCommentsPerPost": self.comments_per_post > 0,
            "maxPostsCount": limit,
            "maxCommentsPerPost": self.comments_per_post,
        }

    def _run_actor(self, payload: dict[str, Any]) -> list[Any]:
        actor = urllib.parse.quote(self.actor_id.replace("/", "~"), safe="~")
        request = urllib.request.Request(
            f"{self.base_url}/acts/{actor}/run-sync-get-dataset-items",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "User-Agent": "CampusYamu-CareerResearch/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Apify HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Apify request failed: {exc.reason}") from exc
        if not isinstance(data, list):
            raise RuntimeError("Apify returned an invalid dataset response")
        return data


def reddit_documents(
    items: list[Any],
    query: SearchQuery,
    limit: int,
) -> list[WebDocument]:
    """Group actor items into one document per post with its top comments."""

    posts: dict[str, dict[str, Any]] = {}
    comments: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("dataType")
        if kind == "post" and _post_url(item) and not _truthy(item.get("over18")):
            posts.setdefault(str(item.get("id") or _post_url(item)), item)
        elif kind == "comment" and item.get("body") and not _is_moderation(item):
            # postId links replies at any depth to their thread.
            parent = item.get("postId") or item.get("parentId") or ""
            comments.setdefault(str(parent), []).append(item)

    documents = []
    for post_id, post in list(posts.items())[:limit]:
        replies = sorted(
            comments.get(post_id, []),
            key=_votes,
            reverse=True,
        )[:COMMENTS_PER_DOCUMENT]
        documents.append(
            WebDocument(
                url=_clean_reddit_url(_post_url(post)),
                title=str(post.get("title") or "").strip(),
                description=str(post.get("body") or "").strip()[:300],
                markdown=_post_markdown(post, replies),
                query=query.text,
                query_category=query.category,
                result_type="reddit",
                domain="reddit.com",
                source_tier=COMMUNITY_TIER,
                trusted=False,
            )
        )
    return documents


def _post_markdown(post: dict[str, Any], replies: list[dict[str, Any]]) -> str:
    community = post.get("communityName") or ""
    lines = [
        f"# {str(post.get('title') or '').strip()}",
        "",
        (
            f"Community discussion (anecdotal) | {community} | "
            f"posted {str(post.get('createdAt') or 'unknown')[:10]} | "
            f"{_votes(post)} upvotes | "
            f"{_number(post.get('commentsCount', post.get('numberOfComments')))} comments"
        ),
        "",
        str(post.get("body") or "").strip() or "(no post body)",
    ]
    if replies:
        lines.extend(("", "## Top comments"))
        for reply in replies:
            body = " ".join(str(reply.get("body") or "").split())
            date = str(reply.get("commentCreatedAt") or reply.get("createdAt") or "")[:10]
            lines.append(f"- ({_votes(reply)} upvotes, {date}) {body}")
    return "\n".join(lines).strip()


def _post_url(post: dict[str, Any]) -> str:
    return str(post.get("postUrl") or post.get("url") or "")


def _votes(item: dict[str, Any]) -> int:
    for key in ("commentUpVotes", "upVotes", "score"):
        if item.get(key) is not None:
            return _number(item[key])
    return 0


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() == "true"
    return bool(value)


def _is_moderation(comment: dict[str, Any]) -> bool:
    return (
        str(comment.get("authorName") or "").casefold() == "automoderator"
        or _truthy(comment.get("stickied"))
        or comment.get("distinguished") == "moderator"
    )


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clean_reddit_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme or "https", parts.netloc.casefold(), parts.path, "", "")
    )
