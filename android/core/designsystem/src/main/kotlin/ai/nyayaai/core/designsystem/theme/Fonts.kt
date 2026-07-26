package ai.nyayaai.core.designsystem.theme

import ai.nyayaai.core.designsystem.R
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight

/**
 * D.4.1 requires type that "must render Devanagari cleanly". Inter has no Devanagari
 * coverage, so this is Noto Sans — bundled, not requested from the system.
 *
 * Bundling matters because Devanagari rendering on budget Indian devices is inconsistent:
 * vendor fonts vary in matra placement and in which conjuncts (क्त, ज्ञ, श्र, त्र) they form
 * correctly. A hearing purpose or a client's name rendered with broken conjuncts looks
 * unprofessional in exactly the market this product is for.
 *
 * These are static instances subsetted from the upstream variable fonts:
 *  - static, because variable-font weight axes need API 26 and `minSdk` is 24;
 *  - subsetted (Latin + Devanagari only), which takes the six files to ~690 KB total
 *    instead of ~2.7 MB, against a 40 MB AAB budget (D.12.2).
 *
 * All Devanagari shaping features are preserved — `akhn`, `half`, `rphf`, `rkrf`, `blwf`,
 * `pres`, `psts`, `abvs`, `blws`, `nukt` — which is what actually forms the conjuncts.
 *
 * Licensed under the SIL Open Font License; see `core/designsystem/LICENSE-fonts.txt`.
 */
val NotoSans =
    FontFamily(
        Font(R.font.noto_sans_regular, FontWeight.Normal),
        Font(R.font.noto_sans_medium, FontWeight.Medium),
        Font(R.font.noto_sans_semibold, FontWeight.SemiBold),
    )

/**
 * Noto Sans Devanagari, which **also carries Latin glyphs** (they were kept in the subset
 * deliberately).
 *
 * That matters because Compose resolves a `FontFamily` to a single typeface and does not
 * do per-script fallback within one family. Hindi UI is full of Hinglish and untranslated
 * proper nouns — "Aaj ki hearings", court names, CNR numbers — so the Hindi locale needs
 * one family that renders both scripts, rather than two families that cannot be combined.
 */
val NotoSansDevanagari =
    FontFamily(
        Font(R.font.noto_sans_devanagari_regular, FontWeight.Normal),
        Font(R.font.noto_sans_devanagari_medium, FontWeight.Medium),
        Font(R.font.noto_sans_devanagari_semibold, FontWeight.SemiBold),
    )
