EXTRACTION_PROMPT = """You are reading a 510(k) summary document, the public
disclosure a device manufacturer files with FDA under 21 CFR 807.92.

The document text is divided into pages by "[Page N]" markers. 
Every predicate and reference-device citation (K-number or name-only) must
include the page number of the marker immediately preceding it, and a
short quote (under 25 words) from that same page proving it.

Your job: extract every predicate device this document claims substantial
equivalence to.

- Predicate vs. reference device: extract predicates into `predicates` /
  `predicates_name_only`. A reference device supports one specific performance
  claim (e.g. "tested against X for tensile strength") and is not the
  substantial-equivalence argument -- those go in `reference_devices`. If a
  document doesn't clearly separate the two (most pre-2000s ones don't),
  default to treating it as a predicate.

- A predicate cited by name only, no K-number: record it in
  `predicates_name_only` with whatever name and applicant the document gives.
  Do not guess a K-number. Note in `extraction_flags` which of three
  reasons applies: 
  (1) ordinary omission -- almost certainly has a real
  K-number, just not stated (K974098's "ProteGen Sling"); 
  (2) pre-1976 device
  that may never have had one at all (K994328's "Bard Mesh (pre-amendment)");
  (3) legally exempt from 510(k) entirely, so it never gets a K-number even
  today (K121819 cites "Mepitac Soft Silicone Tape" marked Class I / exempt
  instead of a K-number).

- A specific NAMED device with no K-number goes in predicates_name_only. An
  unnamed CLASS or group of devices -- "devices marketed prior to 1976,"
  "several commercially available biopsy needles" with none named -- goes in
  generic_bases instead. The test: could a person go look this specific thing
  up? If yes but there's no number, it's predicates_name_only. If there is no
  specific thing to look up, it's generic_bases.

- FDA's own approval letter always contains a standard paragraph invoking the
  pre-1976 / reclassified-devices clause, on every single clearance, whether
  or not a specific predicate was ever named elsewhere in the document. This
  is boilerplate legal language from the agency, not the applicant's
  equivalence argument. Do NOT record it in generic_bases if the document
  ALSO names a specific predicate (by K-number or name) anywhere -- only
  record it when it is the ONLY basis offered, i.e. predicates and
  predicates_name_only are both empty.

- Two or more K-numbers cited together for what reads as one product (e.g.
  "K152416/K171334, Indego, ...") are still two separate entries in
  predicates. Note the pairing in extraction flags so the relationship isn't lost.

- A K-number can be malformed by OCR (wrong digit count, e.g. "K0733394").
  Do NOT guess a corrected number. If the number isn't cleanly readable as K followed
  by 6 digits, put the device in `predicates_name_only` with its name and applicant, and
  note the unreadable number in extraction_flags.

- Same-applicant citations belong in `predicates` too, as long as the
  document actually invokes them as the equivalence basis. Do not exclude
  something just because it shares the applicant or product name with the
  current device.

- A K-number cited to support one specific technical or performance claim
  (e.g. "the app runs on the operating system of the legally marketed
  MD-2300S (K152318)") is a `reference_device`, not a predicate and not
  history -- it's neither the equivalence argument nor this device's own
  regulatory lineage, just a supporting technical dependency.

- Multiple predicates in one document: extract all of them as separate
  entries in the list, equal weight, unless the document itself marks one as
  primary and the others as supporting (K980431 cited three with no ranking --
  treat all three as equal predicates).

- A document that names no predicate AND invokes no generic basis at all --
  true silence, nothing to point to: set found_nothing=true, leave
  predicates, reference_devices, and generic_bases all empty. This does not
  necessarily mean low-confidence, that should be treated as an independent
  judgment.

- The document's own K-number: never a predicate, even if it appears in the
  text (headers, footers, running titles all repeat it).

- extraction_flags: ONE short sentence, ONLY when something is genuinely
  ambiguous, atypical, or required a judgment call (self-citation lineage,
  malformed K-numbers, exemption reasoning, anything not covered cleanly
  by the rules above). Leave it empty on ordinary, unambiguous
  extractions.

- A cited number in BK###### format: not a CDRH 510(k) K-number -- it's a
  CBER-reviewed biologics clearance in a different numbering series. Do not
  put it in predicates. Note it in extraction flags if it appears.

Document (K-number {k_number}):
---
{document_text}
---

Return your answer as structured output matching the Extraction schema."""