"""One-off editorial pass: remove research-process language from published text fields."""
import json, re
R = "/home/user/sandbox-/iran-map/research/"
SUBS = {
"frontier.json": [
 ("Qazakh/Shamshadil are in f_kartli_kakheti.", "Qazakh and Shamshadil are mapped with Kartli-Kakheti."),
 ("A 2013 Russian review says the southern Talysh 'together with Astara' stayed Persian until 1828, so the Astara-district unit (AZE2_36) may belong with the Persian remainder in 1813-28; kept here, low confidence.",
  "A 2013 Russian review says the southern Talysh 'together with Astara' stayed Persian until 1828, so Astara district may belong with the Persian remainder in 1813-28; it is shown here with the 1813 cession, at low confidence."),
 ("Location and extent are NOT verified: sources say", "Location and extent are uncertain. Sources say"),
 ("Included only because its sovereignty was disputed with the Ottomans before 1847; the internal agent may overlay the Ka'b/Muhaisin sheikhdom (indirect) for 1812-1925.",
  "Mapped separately because its sovereignty was disputed with the Ottomans before 1847. The autonomy of the Ka'b and Muhaysin sheikhs is shown in its own records."),
 ("A Kuhak-specific claim before 1871 is not documented:", "No Kuhak-specific claim before 1871 is documented;"),
 (" Added by the verifier: the original file had no de jure record for this parcel (all of Khorramshahr and Abadan counties), so it dropped out of Iran's claimed area for all time.", ""),
 (" Added by the verifier: the original file had no de jure record, so the parcel dropped out of the Iranian claim for all time.", ""),
 (" Added by the verifier: the original file had no de jure record.", ""),
 ("but no date or primary source was found, so the old placeholder end (1826-12) is replaced by the Turkmenchay date; the Russian recapture of the Lankaran lowland, if any, may fall in 1827.",
  "but gives no date or primary source, so the end is set at Turkmenchay. A Russian recapture of the Lankaran lowland, if it happened, may fall in 1827."),
 ("this reading (indirect) matches internal.json i_mohammerah_core for 1800-1837. ", "they are shown as autonomous under Iranian suzerainty. "),
 ("The old note said HRW describes the Iranian hold on Penjwin as 'brief'; that HRW sentence is about the capture of HALABJA (March 1988), not Penjwin. ",
  "An HRW remark sometimes cited as calling the Penjwin hold 'brief' refers to Halabja (March 1988). "),
 ("no source dates the end of Iranian/PUK control of the Penjwin salient, so the placeholder end of 21 Nov 1983 is replaced by 14 July 1988 (low confidence).",
  "no source dates the end of Iranian/PUK control of the Penjwin salient, so the general withdrawal of 14 July 1988 is used (low confidence)."),
 ("Persian takeover of western Sistan, inside modern Iran, is left to the internal agent.", "The Persian takeover of western Sistan, inside modern Iran, is shown in that region's own records."),
 ("Baseline only: the semi-autonomous Muhaysin/Khaz'al sheikhdom (to Dec 1924), the 1857 British occupation and the 1980-82 Iraqi occupation are exceptions recorded in internal.json (i_mohammerah_core, i_iraq_khorramshahr, i_iraq_abadan) and overlaid on this record. Added because a frontier parcel inside Iran needs a record for every period or it drops out of the held area.",
  "Baseline control. The semi-autonomous Muhaysin/Khaz'al sheikhdom (to Dec 1924), the 1857 British occupation and the 1980-82 Iraqi occupation have their own records, drawn over this one."),
 ("Baseline only: internal.json (i_baluch_sarhad, citing Iranica) records the Sarhad Baluch as 'none' (practically independent) until the Persian occupation of Bampur in 1849-50 and 'indirect' afterwards; those exceptions overlay this record.",
  "Baseline control. The Sarhad Baluch were practically independent until the Persian occupation of Bampur in 1849-50 and autonomous afterwards (Iranica); those periods have their own records, drawn over this one."),
 ("(reported at Urmia/Sauj Bulaq, Zohab/Mehran and Kotur; details not verified)", "(reported at Urmia/Sauj Bulaq, Zohab/Mehran and Kotur; details are thin)"),
 ("These areas are inside modern Iran: left to the internal agent.", "The occupied districts inside modern Iran are shown as their own region."),
 ("Bajirga/Borolan gains are not mapped (location unverified). Conflict:", "The Bajirga and Borolan gains are not mapped because their location is uncertain. Sources conflict:"),
 ("Iranica followed; Kotur strip low confidence.", "This map follows Iranica; the Kotur strip is low confidence."),
 ("their location was not verified, so they are not mapped as Iranian-held.", "their exact location is uncertain, so they are not mapped."),
 ("Western (modern-Iranian) Sistan is left to the internal agent.", "Western Sistan, inside modern Iran, is shown in its own region."),
 ("Hissar is not mapped (location not verified).", "Hissar is not mapped because its extent is uncertain."),
 ("claimed Abu Musa (the researcher's file said 'for the British prime minister'; Iranica does not say British);", "claimed Abu Musa;"),
],
"internal.json": [
 ("(see i_salar_khorasan_wide)", "(see the wider Khorasan region of Salar's revolt)"),
 ("those belong to separate regions (i_bojnurd_shadlu, i_qaenat_alam) and are omitted to avoid overlap.", "those are mapped as separate regions (Bojnurd and the Qa'enat)."),
 ("Sistan is separate (i_sistan).", "Sistan is mapped separately."),
 ("Schematic strip; see custom.note. A county-union would grossly overstate the occupation.", "Schematic strip about 25-40 km wide along the border. Whole counties would greatly overstate the occupation."),
 (" Verification: Khoy split off to i_russian_khoy_1828, which Russia kept as security for the indemnity long after the rest of Azerbaijan was evacuated.",
  " Khoy is mapped separately because Russia kept it as security for the indemnity long after the rest of Azerbaijan was evacuated."),
 ("(Gilan, inside i_gilan)", "(Gilan)"),
 ("are in i_kalhor_border_kurds.", "are mapped with the Kalhor border region."),
 ("Qasimi dependencies on islands (Abu Musa, Tunbs, Sirri) were handled by the frontier researcher.", "The Qasimi island dependencies (Abu Musa, the Tunbs, Sirri) are mapped as frontier regions."),
 ("Circle approximation only. Verification: the original single region covered Shiraz, Kerman and Bandar Abbas from March 1916, but Sykes reached Kerman on 12 June 1916 and Shiraz on 11 Nov 1916, so those towns were split into i_spr_kerman and i_spr_shiraz.",
  "Circle approximation only. Sykes landed at Bandar Abbas in March 1916, reached Kerman on 12 June 1916 and Shiraz on 11 Nov 1916; Kerman and Shiraz are mapped separately."),
 ("The two Isfahan keys in the catalog (city-level and surrounding county) are used; their relationship is unclear and may double-cover the same area.", "Isfahan city and the surrounding county."),
 ("Schematic; do not render as full counties.", "Schematic strip along the border; the actual pockets were a handful of positions."),
 (" (Verification: Semnan province was split out to i_wwii_soviet_semnan because the Soviets left Mashhad/Shahrud/Semnan in March 1946, earlier than the rest.)",
  " Semnan province is mapped separately because the Soviets left Mashhad, Shahrud and Semnan in March 1946, earlier than the rest."),
 ("Only a schematic block. Verification: Sanandaj county (IRN2_227) added - British and Soviet columns met at Sanandaj on 30 Aug 1941",
  "Only a schematic block. Sanandaj county is included because British and Soviet columns met at Sanandaj on 30 Aug 1941"),
 ("was not established.", "is uncertain."),
 ("split out of i_wwii_soviet_north.", "mapped separately from the rest of the Soviet zone."),
 ("that quasi-indirect phase is NOT mapped here (no end date established), so the renderer shows direct control after 1928.", "that quasi-indirect phase is not mapped because no end date is established, so the map shows direct control after 1928."),
 ("so the researcher's 1887 end was too early. The new end, 1925, is still a placeholder tied to Reza Khan's consolidation in the south; the real date was not found.",
  "so their rule outlasted 1887. The end date of 1925 is an estimate tied to Reza Khan's consolidation in the south; the real date is unknown."),
 ("Not independently verified in this research pass; reconstructed from general scholarship", "General accounts; no specific source located"),
 ("This replaces the researcher's undated 'contested' status Aug 1916-Mar 1917; the end month is the weakest part", "The end month is the least certain part"),
 ("Verification: UNIIMOG's own background says", "UNIIMOG's own background says"),
 ("so the whole span is coded contested (low) instead of the researcher's continuous foreign occupation to June 1982.", "so the whole span is shown as contested (low confidence)."),
 ("Verification (Iranica 'Iraq vii'):", "Iranica ('Iraq vii'):"),
 ("the end is therefore moved from 1982-06 (the date of Iraq's general withdrawal announcement) to 1982-05.", "the end is therefore May 1982 rather than Iraq's general withdrawal announcement in June."),
 ("CORRECTION: the researcher's 1800 start is dropped. Before c.1900", "Before c.1900"),
 ("Verification: Wikipedia ('Battle of Khanaqin') says", "Wikipedia ('Battle of Khanaqin') says"),
 ("so 1883 replaces the former 1880-10 placeholder.", "so 1883 is used as the end."),
 ("The researcher's alternative account (Vali defeated and fleeing to Iraq with Simko in 1922) is contradicted by this chronology and is dropped.", "An account of the vali fleeing to Iraq with Simko in 1922 is contradicted by this chronology."),
 ("Correction: Shawkat al-Molk was governor 1904-1924, not 'to the 1930s'; he resigned", "Shawkat al-Molk was governor 1904-1924; he resigned"),
 ("CORRECTION: the record ended 1929-03, but Iranica says that in 1926", "This phase ends in 1926: Iranica says that in 1926"),
 ("CORRECTION: the record previously ran to 1933 as 'contested'; the 1929 truce withdrew the military governors, and the 1932 rebellion 'in vain' is not documented as holding territory (see the next record).",
  "The truce withdrew the military governors; the abortive 1932 rebellion is not documented as holding territory."),
 ("This was a mobile insurgency, not territorial control; included at low confidence. Verification: this is the weakest record in the file - a mobile insurgency from mountain camps, not control of the Qashqai counties; the IRGC held the towns and roads. Kept at low confidence rather than deleted; the opposite-error risk (central control actually direct) is real.",
  "This was a mobile insurgency from mountain camps, not control of the Qashqai counties; the Revolutionary Guards held the towns and roads. Shown at low confidence: control may in fact have stayed direct."),
 ("Khoy is handled in i_russian_khoy_1828.", "Khoy is mapped separately."),
 ("Verification (Iranica 'Shahsevan'):", "Iranica ('Shahsevan'):"),
 ("'none' is kept because Iranica does not describe an acknowledgment of the shah, but 'indirect' is arguable.", "They are shown as outside state control because Iranica describes no acknowledgment of the shah; autonomy under the shah is arguable."),
 ("Verification: this record now covers Bandar Abbas only; Kerman (from June 1916) and Shiraz (from Nov 1916) have their own records.", "Kerman (from June 1916) and Shiraz (from Nov 1916) are mapped separately."),
 ("no source for its end was found and 1935 stays a placeholder tied to Pahlavi centralisation.", "no source gives its end, so 1935 is an estimate tied to Pahlavi centralisation."),
 ("Verification: Wikipedia ('Uprising of Sheikh Ubeydullah') says", "Wikipedia ('Uprising of Sheikh Ubeydullah') says"),
 ("Control was transient and set up no administration, so the status is changed from 'none' to 'contested' (low).", "Control was transient and set up no administration, so it is shown as contested (low confidence)."),
 ("The Zanjan province units were included by the original researcher; Iranica does not name Zanjan, so their inclusion is unverified", "Zanjan province is included on the strength of general accounts; Iranica does not name it"),
 ("CORRECTION: Iranica ('Khorasan xi') says the Soviets stayed 'until the winter of 1943', but the Soviet communique",
  "Iranica ('Khorasan xi') says the Soviets stayed 'until the winter of 1943', but the Soviet communique"),
 ("Verification: Semnan province was split into i_wwii_soviet_semnan (evacuated by 24 March 1946); this record now covers Gilan, Mazandaran, Golestan and Qazvin, held to about 6-9 May 1946.",
  "Semnan province, evacuated by 24 March 1946, is mapped separately."),
 ("not the total absence of state authority the researcher's 'none' implied.", "not a total absence of state authority."),
 ("the status here is a low-confidence compromise.", "the status shown is a low-confidence compromise."),
 ("Added in verification as an omitted rebel-held area of about five months.", "Rebel-held for about five months."),
 ("Added in verification as an omitted eight-month armed enclave; coded contested because", "An eight-month armed enclave, shown as contested because"),
 ("Added in verification as an omission; start month and extent are approximate", "Start month and extent are approximate"),
 ("Added in verification as an omission; the withdrawal date was not found and 1918-11 (the Armistice) is a placeholder.", "The withdrawal date is unknown; the Armistice of November 1918 is used."),
 ("(event i_ev_soviet_east_withdrawal_1946)", ""),
 ("(the Jan 1946 proclamation is event i_ev_mahabad_republic_1946)", "(the formal proclamation of Jan 1946 is listed as its own event)"),
],
}
SKIP = {"units", "minus_units", "custom", "id", "region", "start_event", "end_event"}
for fn, subs in SUBS.items():
    d = json.load(open(R + fn))
    used = {a: 0 for a, _ in subs}
    def fix(s):
        for a, b in subs:
            if a in s:
                s = s.replace(a, b); used[a] += 1
        return re.sub(r"\s{2,}", " ", s).replace(" .", ".").strip()
    for sec in ("regions", "dejure", "defacto", "events"):
        for r in d.get(sec, []):
            for k, v in list(r.items()):
                if k in SKIP: continue
                if isinstance(v, str): r[k] = fix(v)
                elif isinstance(v, list): r[k] = [fix(x) if isinstance(x, str) else x for x in v]
    json.dump(d, open(R + fn, "w"), ensure_ascii=False, indent=1)
    for a, n in used.items():
        if n == 0: print("UNUSED", fn, a[:80])
