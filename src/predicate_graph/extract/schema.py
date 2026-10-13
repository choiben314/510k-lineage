from pydantic import BaseModel, Field, field_validator

class Citation(BaseModel):
    """A K-number citation with page-level provenance"""
    k_number: str
    page: int = Field(description="Page number from the nearest preceding [Page N] marker.")
    quote: str = Field(description="Shortest verbatim span, under 25 words, from that page, proving this citation.")

    @field_validator("k_number")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return v.strip().upper()

class NamedPredicate(BaseModel):
    """A predicate cited by trade name only, no K-number given, for cases when unresolvable
    from the document alone."""
    name: str
    applicant: str | None = None
    page: int = Field(description="Page number from the nearest preceding [Page N] marker.")
    quote: str = Field(description="Shortest verbatim span, under 25 words, from that page, proving this citation.")

class Extraction(BaseModel):
    k_number: str

    predicates: list[Citation] = Field(
        description="K-numbers cited as the substantial-equivalence predicate, "
        "whether formally 'primary' or 'additional/secondary', include all of them, grounded to the cited page and quote."
    )

    predicates_name_only: list[NamedPredicate] = Field(
        default_factory=list,
        description="List of predicate names (not the K-numbers), if given"
    )

    reference_devices: list[Citation] = Field(
        description="A reference device supports one performance claim; it is NOT the substantial-equivalence predicate."
    )
    reference_devices_name_only: list[NamedPredicate] = Field(
        default_factory=list,
        description="Trade names of reference devices, if given (not K-numbers)."
    )

    generic_bases: list[str] = Field(
        default_factory=list,
        description="Equivalence claimed against an unnamed CLASS of devices, not "
        "one specific device, such as 'devices marketed in interstate commerce prior to May 28, 1976' (the blanket grandfather clause), or 'several "
        "commercially available biopsy needles' with no names given. Real, meaningful equivalence claims but not resolvable to any K-number or device name. "
        "Record the exact phrase used. Do not put these in predicates_name_only or reference_devices_name_only, and only populate it when it is the sole basis offered."
    )

    found_nothing: bool = Field(
        description="True ONLY when the document states no equivalence basis. "
        "A document invoking the pre-1976 blanket clause or citing an unnamed device class is NOT found_nothing=true; that goes in generic_bases instead."
    )

    extraction_flags: str = Field(
        default="",
        description="ONE short sentence, only when something required a genuine "
        "judgment call. Leave empty on ordinary, unambiguous "
        "extractions, do not narrate what evidence already shows."
    )