# TCIA data-route inquiry (READY TO SEND — NOT SENT)

| Field | Value |
|---|---|
| Status | **Final draft, not sent.** It is **not required** for the approved B1 route. On 2026-10-01, B1 was authorized through the owner-approved alternative (amendment v1.0-A1; source class `OWNER_APPROVED_ALTERNATIVE`; external provider authorization NONE). The inquiry stays available if the owner later wants TCIA's position on private third-party storage (route A), which remains **not authorized**. If sent, the owner sends it manually from their own email account. |
| To | help@cancerimagingarchive.net, the TCIA Helpdesk address on the official Support page (verified 2026-09-29 and 2026-09-30) |
| Purpose | Gate B1 of protocol v1.0: written guidance on the permitted data route |
| Effect of sending | None on the gates. A reply would be recorded as separate `EXTERNAL_PROVIDER_AUTHORIZATION` evidence and would not alter the owner-approved route already in force. |
| After sending | Record the send date in [B1_DATA_ROUTE_AUTHORIZATION.md](B1_DATA_ROUTE_AUTHORIZATION.md) §7. Set `data.inquiry_sent: true` in `docs/project_status.yaml`. |

Before sending, replace the four bracketed fields: `[Date]`, `[Full name]`, `[Affiliation / institution]` and `[Contact email]`. Add no personal data beyond what you want TCIA to have. Send the text between the two horizontal rules as a plain-text email.

---

**To:** help@cancerimagingarchive.net

**Subject:** Permitted data route for RSNA-ASNR-MICCAI-BraTS-2021 (DOI 10.7937/jc8x-9874): private computational storage vs runtime-only access

Date: [Date]

Dear TCIA Helpdesk,

I am planning an academic research study on brain-tumour segmentation and case-level uncertainty under missing MRI sequences. The study protocol is pre-registered.

The study would use the RSNA-ASNR-MICCAI-BraTS-2021 analysis result (DOI 10.7937/jc8x-9874), specifically:

- the "Challenge data both tasks" package;
- the "ID Crosswalk map between BraTS ID and TCIA ID".

The data would be used solely for academic research. Only case identifiers, file hashes, case counts and aggregate metrics would be published. No re-identification or facial rendering would be attempted.

Model training would run on a third-party cloud notebook platform (Kaggle, possibly Google Colab). Before acquiring any data, I would like your written guidance.

To be precise, I distinguish three things:

- **(A) Private computational storage.** An access-restricted copy of the official files is kept in a third-party computational environment, for example as a private Kaggle dataset. It is visible only to me, it is never shared or made public, and it is used only as input to my own computations.
- **(B) Public redistribution.** Making the files available to anyone else in any form: public datasets, shared links, public mirrors or re-uploads. **I do not intend to do this.**
- **(C) Runtime-only access.** The files are downloaded from the official TCIA source directly into the temporary storage of a compute session at runtime. No persistent copy is kept on the third-party platform after the session ends.

My questions:

1. Is a private, access-restricted copy of the official BraTS 2021 files in a third-party computational environment such as Kaggle, as in (A), permitted for the sole purpose of academic research?
2. Would TCIA consider such private computational storage (A) to be "mirroring", "re-hosting" or another activity that falls under the TCIA Data Analysis Center guidance? If so, what would be required?
3. Is runtime-only downloading into an approved compute environment, without persistent third-party storage, as in (C), acceptable?
4. Beyond the CC BY 4.0 licence, the required data citation and the TCIA Data Usage Policies, do any additional attribution, citation, access-restriction, retention/deletion or downstream-use conditions apply?
5. If private third-party storage (A) is not acceptable, which TCIA-approved alternative route should I use to work with this dataset on cloud GPU compute?
6. Can the official TCIA access route for this dataset be used directly from a computational environment, such as a cloud notebook session? The challenge-data download lists the IBM Aspera Connect plugin as a requirement. Is there a supported programmatic or command-line method (for example the TCIA REST API or a command-line Aspera client) suitable for such an environment?

I will not acquire any data until I have your reply, and I will follow whichever route you indicate.

Thank you for your help.

Kind regards,
[Full name]
[Affiliation / institution]
[Contact email]

Reference pages:
- https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/
- https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/
- https://www.cancerimagingarchive.net/tcia-data-analysis-center/

---

## Notes for the owner

- The official Support page asks requests to include your contact information and the URL of the relevant page. Both are included above.
- Keep the full reply privately. The committed evidence file, `docs/data/B1_EVIDENCE_<response date>.md` (made from [B1_EVIDENCE_TEMPLATE.md](B1_EVIDENCE_TEMPLATE.md)), must quote the relevant sentences of the reply verbatim. Redact personal contact details other than the official support address.
- Sending this inquiry, or receiving an automatic acknowledgement, does **not** change B1.
- B1 passes (shown as "Authorized") only through `brats-uncertainty gate-transition B1 PASSED …`, run on a committed or staged evidence file that records an actual written authorization with `Authorization status: AUTHORIZED` and `Conclusion: APPROVED`.
- If the reply refuses the route or is unclear, B1 does not pass. Ask a follow-up question, or record the refusal as described in the template.
- None of these is a substitute for the reply: public downloadability, a TCIA web page, the CC licence, Kaggle availability, a successful test download, or API availability.
