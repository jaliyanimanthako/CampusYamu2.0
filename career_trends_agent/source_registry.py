"""Classify discovered pages without treating every web result as authoritative."""

from __future__ import annotations


DOMAIN_TIERS = {
    # Live Sri Lankan demand
    "topjobs.lk": "local_live_jobs",
    "xpress.jobs": "local_live_jobs",
    "jobber.lk": "local_live_jobs",
    "linkedin.com": "local_live_jobs",
    # Sri Lankan official and field-specific evidence
    "statistics.gov.lk": "local_official",
    "cbsl.gov.lk": "local_official",
    "health.gov.lk": "local_official",
    "slmc.gov.lk": "local_official",
    "daph.gov.lk": "local_official",
    "moj.gov.lk": "local_official",
    "moe.gov.lk": "local_official",
    "env.gov.lk": "local_official",
    "basl.lk": "local_professional_body",
    "casrilanka.com": "local_professional_body",
    "agrimin.gov.lk": "local_official",
    "sltda.gov.lk": "local_official",
    "cida.gov.lk": "local_official",
    "iesl.lk": "local_professional_body",
    "slasscom.lk": "local_professional_body",
    # Postgraduate and scholarship bodies
    "ugc.ac.lk": "local_official",
    "pgim.cmb.ac.lk": "local_official",
    "chevening.org": "global_official",
    "cscuk.fcdo.gov.uk": "global_official",
    "daad.de": "global_official",
    "studyinjapan.go.jp": "global_official",
    # Anecdotal community discussion: useful signals, never authoritative
    "reddit.com": "community_discussion",
    # International and future outlook
    "onetonline.org": "global_official",
    "onetcenter.org": "global_official",
    "bls.gov": "global_official",
    "weforum.org": "global_outlook",
    "worldbank.org": "global_official",
    "ilo.org": "global_official",
    "who.int": "global_official",
    "fao.org": "global_official",
    "unesco.org": "global_official",
}

FIELD_SOURCE_DOMAINS = {
    "medicine": ("health.gov.lk", "slmc.gov.lk", "who.int"),
    "allied_health": ("health.gov.lk", "who.int"),
    "nursing": ("health.gov.lk", "who.int"),
    "dentistry": ("health.gov.lk", "slmc.gov.lk", "who.int"),
    "veterinary": ("daph.gov.lk", "fao.org"),
    "law": ("basl.lk", "moj.gov.lk"),
    "finance": ("casrilanka.com", "cbsl.gov.lk"),
    "built_environment": ("cida.gov.lk", "cbsl.gov.lk"),
    "agriculture": ("agrimin.gov.lk", "fao.org"),
    "food_science": ("agrimin.gov.lk", "fao.org"),
    "tourism": ("sltda.gov.lk",),
    "education": ("moe.gov.lk", "unesco.org"),
    "information_technology": ("slasscom.lk", "worldbank.org"),
    "engineering": ("iesl.lk", "cbsl.gov.lk"),
    "environment": ("env.gov.lk", "fao.org", "worldbank.org"),
}


UNTRUSTED_TIERS = frozenset({"community_discussion"})

# Login-walled or media-only sites: scraping returns little or no usable text.
# Reddit is collected separately through its own adapter.
EXCLUDED_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "youtube.com",
)


def is_excluded(domain: str) -> bool:
    normalized = domain.casefold().removeprefix("www.")
    return any(
        normalized == blocked or normalized.endswith(f".{blocked}")
        for blocked in EXCLUDED_DOMAINS
    )


def classify_domain(domain: str) -> tuple[str, bool]:
    normalized = domain.casefold().removeprefix("www.")
    for registered_domain, tier in DOMAIN_TIERS.items():
        if normalized == registered_domain or normalized.endswith(f".{registered_domain}"):
            return tier, tier not in UNTRUSTED_TIERS
    return "other", False
