import type { Translations } from "./en.ts";

export const si: Translations = {
  // Header
  "brand.subtitle": "ශ්‍රී ලංකා රාජ්‍ය විශ්වවිද්‍යාල සහ වෘත්තීය මාර්ගෝපදේශකය",
  "header.status.checking": "සම්බන්ධ වෙමින්",
  "header.status.demo": "ආදර්ශ මාදිලිය",
  "header.status.offline": "නොබැඳි",
  "header.status.aiReady": "AI සූදානම්",
  "header.status.online": "සජීවී",
  "header.editResults": "ප්‍රතිඵල සංස්කරණය",
  "header.reset": "නව / යළි සකසන්න",
  "header.shortlist": "මගේ ලැයිස්තුව ({count})",
  "header.languageLabel": "භාෂාව",
  "theme.light": "ආලෝක",
  "theme.dark": "අඳුරු",
  "theme.switchToDark": "අඳුරු තේමාවට මාරු වන්න",
  "theme.switchToLight": "ආලෝක තේමාවට මාරු වන්න",

  // App
  "app.intakeTitle": "ශිෂ්‍ය තොරතුරු සහ උ/පෙළ ප්‍රතිඵල",
  "app.intakeSubtitle":
    "ශ්‍රී ලංකාවේ රාජ්‍ය විශ්වවිද්‍යාල පාඨමාලා සඳහා ඔබේ සුදුසුකම් සෙවීමට ඔබේ උ/පෙළ විෂය ධාරාව, විෂයයන්, සාමාන්‍ය පොදු පරීක්ෂණ ලකුණු සහ දිස්ත්‍රික්කය ඇතුළත් කරන්න.",
  "app.tab.recommended": "නිර්දේශිත පිළිවෙල",
  "app.tab.bands": "මට්ටම් අනුව සියලු සුදුසුකම්",

  // ProfileForm — Loading / Offline / Demo
  "form.loadingOptions": "විෂය ධාරා, විෂයයන් සහ දිස්ත්‍රික්ක පූරණය වෙමින්…",
  "form.offlineTitle": "අපගේ සේවාදායක යාවත්කාලීන වෙමින් පවතී",
  "form.offlineHint":
    "ඔබට දැන්ම ආදර්ශ ප්‍රතිඵල ගවේෂණය කළ හැක, නැතහොත් මොහොතකින් නැවත සම්බන්ධ වන්න.",
  "form.retryConnection": "නැවත උත්සාහ කරන්න",
  "form.useDemoData": "ආදර්ශ ප්‍රතිඵල ගවේෂණය කරන්න",
  "form.demoBanner":
    "ආදර්ශ මාදිලිය: නියැදි විශ්වවිද්‍යාල දත්ත සමඟ පෙන්වයි. සම්බන්ධ වූ විට සජීවී මාදිලියට මාරු විය හැක.",
  "form.switchLiveApi": "සජීවී මාදිලියට මාරු වන්න",

  // ProfileForm — Section 1
  "form.sec1.title": "1. උ/පෙළ විෂය ධාරාව සහ විෂයයන්",
  "form.sec1.subtitle":
    "ඔබේ උ/පෙළ විෂය ධාරාව සහ වෙනස් විෂයයන් තුනක් සාමාර්ථ සමඟ තෝරන්න.",
  "form.streamLabel": "උ/පෙළ විෂය ධාරාව",
  "form.subjectSlot": "විෂයය {n}",
  "form.selectSubject": "විෂයය තෝරන්න…",
  "form.gradeOption": "සාමාර්ථය {grade}",
  "form.softNotice.requiredAll":
    "{stream} සඳහා සාමාන්‍යයෙන් {subjects} ඇතුළත් වේ. ඔබේ විෂය සංයෝජනය වලංගු නම් ඉදිරිපත් කළ හැක.",
  "form.softNotice.requiredAny":
    "{stream} සඳහා සාමාන්‍යයෙන් මේවායින් එකක්වත් ඇතුළත් වේ: {subjects}.",
  "form.softNotice.allowed":
    "{subjects} යනු සාමාන්‍ය {stream} විෂය කට්ටලයෙන් බැහැර වේ. එසේ වුවද ඉදිරිපත් කළ හැක.",

  // ProfileForm — Section 2
  "form.sec2.title": "2. විභාග ලකුණු සහ සා/පෙළ අවශ්‍යතා",
  "form.cgtLabel": "සාමාන්‍ය පොදු පරීක්ෂණ (CGT) ලකුණු",
  "form.cgtPlaceholder": "0 – 100",
  "form.cgtHelp":
    "අනිවාර්ය පූර්ණ සංඛ්‍යාවකි (0–100). සමත් ලකුණට වඩා අඩු නම් කිසිදු පාඨමාලාවකට සුදුසුකම් නොලැබේ.",
  "form.zscoreLabel": "Z-ලකුණ (Z-Score)",
  "form.optional": "(විකල්ප)",
  "form.zscorePlaceholder": "උදා. 1.5623",
  "form.zscoreHelp":
    "Z-ලකුණක් නොමැතිව, සුදුසුකම් ලබන පාඨමාලා 'ඉතිහාසයක් නැත' යටතේ පෙන්වයි.",
  "form.olToggle": "සා/පෙළ සාමාර්ථ (විකල්ප — විද්‍යාව, ඉංග්‍රීසි, ගණිතය)",
  "form.olSubjectLabel": "සා/පෙළ {subject}",
  "form.notSpecified": "සඳහන් කර නැත",

  // ProfileForm — Section 3
  "form.sec3.title": "3. දිස්ත්‍රික්කය සහ පදිංචි ස්ථානය",
  "form.sec3.subtitle":
    "ප්‍රවේශ දිස්ත්‍රික්කය Z-ලකුණු කඩඉම් තීරණය කරයි; ගමන් කාලය ඇස්තමේන්තු කිරීමට ප්‍රාදේශීය ලේකම් කොට්ඨාසය භාවිතා වේ.",
  "form.admissionDistrict": "ප්‍රවේශ දිස්ත්‍රික්කය",
  "form.homeDistrict": "පදිංචි දිස්ත්‍රික්කය",
  "form.dsDivision": "ප්‍රාදේශීය ලේකම් කොට්ඨාසය",

  // ProfileForm — Section 4
  "form.sec4.title": "4. වෘත්තීය සහ විෂය රුචිකත්වයන්",
  "form.preferencesPlaceholder":
    "විකල්ප: උදා. මෘදුකාංග ඉංජිනේරු විද්‍යාව, දත්ත විද්‍යාව, රොබෝ තාක්ෂණය, හෝ මහනුවරට ආසන්නව",
  "form.useLlmTitle": "මගේ රුචිකත්වයන් විශ්ලේෂණයට AI භාවිතා කරන්න",
  "form.useLlmHint":
    "AI මාදිලිය වඩාත් නිවැරදි ගැලපීම් ලබා දෙන නමුත් සාමාන්‍යයෙන් තත්පර 20–40ක් ගත වේ.",

  // ProfileForm — Submit & Validation
  "form.sessionNote":
    "පිටුව නැවුම් කිරීමේදී වාර්තාව නැති නොවන පරිදි ප්‍රතිඵල බ්‍රව්සර් සැසියේ සුරැකේ.",
  "form.analyzing": "සුදුසුකම් ලබන පාඨමාලා විශ්ලේෂණය වෙමින් ({seconds}s)…",
  "form.submitting": "වාර්තාව සකසමින්…",
  "form.submit": "සුදුසු පාඨමාලා සොයන්න",
  "form.err.stream": "කරුණාකර උ/පෙළ විෂය ධාරාවක් තෝරන්න.",
  "form.err.alAll": "කරුණාකර උ/පෙළ විෂයයන් තුනම තෝරන්න.",
  "form.err.alDistinct": "කරුණාකර වෙනස් උ/පෙළ විෂයයන් තුනක් තෝරන්න.",
  "form.err.alGrades": "කරුණාකර සෑම උ/පෙළ විෂයයකටම සාමාර්ථයක් තෝරන්න.",
  "form.err.cgt":
    "සාමාන්‍ය පොදු පරීක්ෂණ (CGT) ලකුණ 0 සහ 100 අතර පූර්ණ සංඛ්‍යාවක් විය යුතුය.",
  "form.err.zscore": "Z-ලකුණ වලංගු සංඛ්‍යාවක් විය යුතුය (උදාහරණයක් ලෙස 1.5623).",
  "form.err.admissionDistrict": "කරුණාකර ප්‍රවේශ දිස්ත්‍රික්කයක් තෝරන්න.",
  "form.err.dsDivision": "කරුණාකර ඔබේ ප්‍රාදේශීය ලේකම් කොට්ඨාසය තෝරන්න.",
  "form.err.preferencesMax": "රුචිකත්වයන් අක්ෂර 2000කට වඩා අඩු විය යුතුය.",
  "form.err.unexpected": "නිර්දේශ සකසන අතරතුර අනපේක්ෂිත දෝෂයක් ඇති විය.",

  // SummaryStrip
  "summary.noZscore": "Z-ලකුණක් නැත",
  "summary.zscorePrefix": "Z-ලකුණ: {value}",
  "summary.admissionPrefix": "ප්‍රවේශය:",
  "summary.homePrefix": "පදිංචිය:",
  "summary.aiInterests": "AI රුචිකත්වය",
  "summary.readyToApply": "අයදුම් කළ හැක",
  "summary.withConditions": "කොන්දේසි සහිතයි",

  // Bands
  "band.strong": "ඉතා සුදුසු",
  "band.competitive": "තරඟකාරී",
  "band.reach": "උත්සාහ කළ හැක",
  "band.unlikely": "අවස්ථාව අඩුයි",
  "band.no_history": "ඉතිහාසයක් නැත",
  "band.desc.strong":
    "පසුගිය වසරවල කඩඉම් ලකුණු ඔබේ Z-ලකුණින් ඉක්මවා ඇත.",
  "band.desc.competitive":
    "මෑත කඩඉම් ලකුණුවලට ආසන්නයි — ප්‍රතිඵලය දෙපැත්තටම විය හැක.",
  "band.desc.reach": "මෑත කඩඉම් ලකුණුවලට වඩා තරමක් අඩුයි.",
  "band.desc.unlikely": "මෑත කඩඉම් ලකුණුවලට වඩා බෙහෙවින් අඩුයි.",
  "band.desc.no_history":
    "සුදුසුකම් ඇත, නමුත් සැසඳීමට කඩඉම් ඉතිහාසයක් නැත (හෝ Z-ලකුණක් ලබා දී නැත).",

  // RankingsView
  "rankings.tab.distance": "සමබර (නිර්දේශිත)",
  "rankings.tab.preference": "රුචිකත්වය අනුව",
  "rankings.tab.zscore": "ඇතුළත් වීමේ අවස්ථාව අනුව",
  "rankings.showing": "{total} න් {shown} ක් පෙන්වයි",
  "rankings.closeCallsToggle": "ආසන්න තේරීම් සහ විකල්ප උපදෙස්",
  "rankings.closeCallsTitle": "ආසන්න තේරීම්",
  "rankings.prioritiesTitle": "ප්‍රමුඛතා උපදෙස්",
  "rankings.empty": "මෙම පැතිකඩ සඳහා ශ්‍රේණිගත පාඨමාලා නොමැත.",
  "rankings.part.interest": "රුචිකත්වය",
  "rankings.part.cutoff": "කඩඉම්",
  "rankings.part.distance": "දුර",
  "rankings.latestCutoff": "නවතම කඩඉම",
  "rankings.travel": "ගමන් කාලය",

  // BandsExplorer
  "bands.searchPlaceholder": "පාඨමාලාව හෝ විශ්වවිද්‍යාලය සොයන්න…",
  "bands.searchAria": "සුදුසු පාඨමාලා සොයන්න",
  "bands.filter.all": "සියල්ල",
  "bands.filter.canApply": "අයදුම් කළ හැක",
  "bands.filter.withConditions": "කොන්දේසි සහිත",
  "bands.filter.sameDistrict": "එකම දිස්ත්‍රික්කය",
  "bands.empty": "ඔබේ සෙවුමට හෝ පෙරහනට ගැලපෙන පාඨමාලා නොමැත.",
  "bands.badge.withConditions": "කොන්දේසි සහිත",
  "bands.badge.aptitudeTest": "යෝග්‍යතා පරීක්ෂණ",
  "bands.badge.sameDistrict": "එකම දිස්ත්‍රික්කය",

  // CourseDrawer
  "drawer.coursePrefix": "පාඨමාලාව {code}",
  "drawer.closeAria": "පාඨමාලා විස්තර වසන්න",
  "drawer.tab.overview": "දළ විශ්ලේෂණය සහ අත්පොත",
  "drawer.tab.chat": "පාඨමාලා කතාබහ",
  "drawer.tab.career": "වෘත්තීය අනාගතය",

  // CourseOverview
  "overview.aptitudeRequired": "යෝග්‍යතා පරීක්ෂණයක් අවශ්‍යයි",
  "overview.zscoreTitle": "Z-ලකුණු සහ කඩඉම් විශ්ලේෂණය",
  "overview.latestCutoff": "නවතම කඩඉම් ලකුණ",
  "overview.predictedCutoff": "පුරෝකථිත කඩඉම",
  "overview.expectedMargin": "අපේක්ෂිත පරතරය",
  "overview.yearsCleared": "සමත් වූ වසර",
  "overview.proposedIntake": "යෝජිත බඳවාගැනීම්",
  "overview.locationTitle": "ස්ථානය, ගමන් කාලය සහ සා/පෙළ පරීක්ෂාව",
  "overview.byCar": "මෝටර් රථයෙන්",
  "overview.estBus": "ඇස්. බස්",
  "overview.roadDistance": "මාර්ග දුර",
  "overview.olMet": "සා/පෙළ {subject} සපුරා ඇත",
  "overview.olFailed": "සා/පෙළ {subject} සපුරා නැත",
  "overview.olUnknown": "සා/පෙළ {subject} පරීක්ෂා කළ යුතුයි",
  "overview.handbookTitle": "UGC අත්පොත කොටස",

  // CourseChat
  "chat.unavailable":
    "API සේවාදායකයේ AI විශේෂාංග සක්‍රීය කර නොමැති බැවින් පාඨමාලා කතාබහ දැනට ලබා ගත නොහැක.",
  "chat.starter.1": "වෘත්තීය අවස්ථා මොනවාද?",
  "chat.starter.2": "යෝග්‍යතා පරීක්ෂණයක් තිබේද?",
  "chat.starter.3": "සා/පෙළ අවශ්‍යතා මොනවාද?",
  "chat.emptyPrompt":
    "{university} හි {course} පිළිබඳ ඕනෑම ප්‍රශ්නයක් අසන්න — අවශ්‍යතා, යෝග්‍යතා පරීක්ෂණ, කාලසීමාව හෝ වෘත්තීය අවස්ථා.",
  "chat.role.user": "ඔබ",
  "chat.role.assistant": "CampusYamu උපදේශක",
  "chat.sources": "මූලාශ්‍ර",
  "chat.inputPlaceholder": "මෙම පාඨමාලාව ගැන අසන්න…",
  "chat.inputAria": "මෙම පාඨමාලාව ගැන ප්‍රශ්නයක් අසන්න",
  "chat.send": "අසන්න",
  "chat.sending": "යවමින්…",
  "chat.failed": "කතාබහ ඉල්ලීම අසාර්ථක විය. කරුණාකර නැවත උත්සාහ කරන්න.",

  // CareerOutlook
  "career.checking": "{course} සඳහා වෘත්තීය අනාගතය පරීක්ෂා කරමින්…",
  "career.loadError": "වෘත්තීය අනාගතය පූරණය කළ නොහැක.",
  "career.conflict":
    "දැනට වෙනත් පාඨමාලාවක් සඳහා පර්යේෂණ ක්‍රියාත්මක වේ. නව පර්යේෂණයක් ආරම්භ කිරීමට පෙර එය අවසන් වන තෙක් රැඳී සිටින්න.",
  "career.startError": "වෘත්තීය පර්යේෂණය ආරම්භ කිරීමට අසමත් විය.",
  "career.running": "වෘත්තීය පර්යේෂණය ක්‍රියාත්මක වෙමින්…",
  "career.pollingNote": "සෑම තත්පර 5කට වරක් යාවත්කාලීන පරීක්ෂා කෙරේ.",
  "career.failed": "වෘත්තීය පර්යේෂණය අසාර්ථක විය",
  "career.title": "වෘත්තීය අනාගතය — {course}",
  "career.confidence": "විශ්වාසනීයත්වය: {value}",
  "career.sourcesCount": "විශ්ලේෂණය කළ මූලාශ්‍ර: {count}",
  "career.updated": "යාවත්කාලීන කළේ: {date}",
  "career.noneTitle": "තවම සුරැකි වෘත්තීය පර්යේෂණ නැත",
  "career.availableHint":
    "වෙබ් වෘත්තීය පර්යේෂණය මගින් {course} සඳහා වත්මන් ශ්‍රී ලාංකික රැකියා අවස්ථා සහ කර්මාන්ත ඉල්ලුම රැස් කරයි. මෙය සාමාන්‍යයෙන් මිනිත්තු 3–10ක් ගත වන අතර වරකට එක් පාඨමාලාවක් පමණක් ක්‍රියාත්මක වේ.",
  "career.researchBtn": "වෘත්තීය අවස්ථා පර්යේෂණ කරන්න",
  "career.startingBtn": "පර්යේෂණය අරඹමින්…",
  "career.unavailableHint":
    "API සේවාදායකයේ වෙබ් පර්යේෂණ යතුරු වින්‍යාස කර නොමැති බැවින් වෘත්තීය පර්යේෂණය දැනට ලබා ගත නොහැක.",

  // Common / Units
  "unit.min": "මිනි. {n}",
  "unit.hour": "පැය {h}",
  "unit.hourMin": "පැය {h} මිනි. {m}",
  "unit.car": "{t} කාර්",
  "unit.bus": "~{t} බස්",

  // Hero & Home Information
  "hero.badge": "UGC 2024/2025 ශිෂ්‍ය අත්පොත · ශ්‍රී ලංකාව",
  "hero.title": "ඔබේ උ/පෙළ ප්‍රතිඵලවලට ගැලපෙනම රාජ්‍ය විශ්වවිද්‍යාල පාඨමාලාව සොයාගන්න.",
  "hero.subtitle":
    "දිස්ත්‍රික් Z-ලකුණු කඩඉම්, ඔබේ ප්‍රාදේශීය ලේකම් කොට්ඨාසයේ සිට ගමන් කාලය සහ ඔබේ වෘත්තීය රුචිකත්වයන් අනුව සුදුසු සියලු උපාධි පාඨමාලා සසඳන්න.",
  "hero.ctaPrimary": "සුදුසුකම් පරීක්ෂා කරන්න",
  "hero.ctaSecondary": "ක්‍රියා කරන ආකාරය",
  "hero.stat.programmes.value": "100+",
  "hero.stat.programmes.label": "UGC උපාධි පාඨමාලා",
  "hero.stat.districts.value": "25 / 339",
  "hero.stat.districts.label": "දිස්ත්‍රික්ක සහ ප්‍රා.ලේ. කොට්ඨාස",
  "hero.stat.bands.value": "මට්ටම් 5",
  "hero.stat.bands.label": "ඉතා සුදුසු සිට ඉතිහාසයක් නැත දක්වා",
  "hero.stat.languages.value": "EN · සිං · தமிழ்",
  "hero.stat.languages.label": "සම්පූර්ණ ත්‍රෛභාෂික අතුරුමුහුණත",
  "hero.previewTitle": "ඔබේ වාර්තාවට ඇතුළත් දෑ",
  "hero.previewItem1": "පසුගිය දිස්ත්‍රික් කඩඉම් අනුව ඇතුළත් වීමේ සම්භාවිතා මට්ටම්",
  "hero.previewItem2": "ඔබේ නිවසේ සිට කාර් සහ බස් ගමන් කාල ඇස්තමේන්තු",
  "hero.previewItem3": "සෘජු UGC අත්පොත උපුටා දැක්වීම් සහ පාඨමාලා ප්‍රශ්නෝත්තර",
  "hero.featuresTitle": "අනුමාන නොව, නිවැරදි දත්ත මත පදනම්ව",
  "hero.feat1.title": "Z-ලකුණු සහ සුදුසුකම් මට්ටම්",
  "hero.feat1.desc":
    "උ/පෙළ විෂය නීති, CGT සමත් ලකුණු සහ සා/පෙළ අවශ්‍යතා ස්වයංක්‍රීයව පරීක්ෂා කර පාඨමාලා මට්ටම් 5කට වර්ග කරයි.",
  "hero.feat2.title": "සමබර පිළිවෙල සහ ගමන් කාලය",
  "hero.feat2.desc":
    "ඔබේ රුචිකත්වය, ඇතුළත් වීමේ අවස්ථාව සහ ප්‍රාදේශීය ලේකම් කොට්ඨාසයේ සිට ගමන් දුර සමබර කර ආසන්න තේරීම් උපදෙස් ලබා දෙයි.",
  "hero.feat3.title": "අත්පොත උපුටා දැක්වීම් සහ වෘත්තීය අනාගතය",
  "hero.feat3.desc":
    "UGC අත්පොතේ අදාළ කොටස් කියවන්න, උපුටා දැක්වීම් සහිත AI ප්‍රශ්න අසන්න, සහ ශ්‍රී ලංකාවේ රැකියා අවස්ථා පරීක්ෂා කරන්න.",
  "hero.howTitle": "පියවර 3කින් ක්‍රියා කරන ආකාරය",
  "hero.step1.title": "ප්‍රතිඵල ඇතුළත් කරන්න",
  "hero.step1.desc":
    "උ/පෙළ විෂය ධාරාව, විෂයයන් 3, CGT ලකුණු, විකල්ප Z-ලකුණ සහ ප්‍රා.ලේ. කොට්ඨාසය තෝරන්න.",
  "hero.step2.title": "ශ්‍රේණිගත පාඨමාලා බලන්න",
  "hero.step2.desc":
    "සමබර පිළිවෙල සහ මට්ටම් ගවේෂකය අතර මාරු වී දිස්ත්‍රික්කය හෝ සූදානම අනුව පෙරහන් කරන්න.",
  "hero.step3.title": "ඕනෑම පාඨමාලාවක් විමසන්න",
  "hero.step3.desc":
    "අත්පොත නීති, AI කතාබහ සහ වෘත්තීය අනාගතය සඳහා පාඨමාලා පැනලය විවෘත කරන්න.",
  "footer.note": "CampusYamu — UGC ශිෂ්‍ය අත්පොත 2024/2025 මත පදනම්ව.",

  // Wizard, Presets, What-If, Shortlist, Share & Compare
  "form.wizard.step1": "විෂය ධාරාව සහ විෂයයන්",
  "form.wizard.step2": "ලකුණු සහ ස්ථානය",
  "form.wizard.step3": "රුචිකත්වය සහ ඉදිරිපත් කිරීම",
  "form.wizard.next": "ඉදිරියට",
  "form.wizard.back": "ආපසු",
  "form.searchDistrict": "දිස්ත්‍රික්ක සොයන්න…",
  "form.searchDs": "ප්‍රා.ලේ. කොට්ඨාස සොයන්න…",
  "form.interestChipsLabel": "ඉක්මන් රුචිකත්ව ටැග් (එක් කිරීමට තට්ටු කරන්න):",
  "form.aiMilestone1": "1/4 UGC සුදුසුකම් නීති පරීක්ෂා කරමින්…",
  "form.aiMilestone2": "2/4 දිස්ත්‍රික් 25හි Z-ලකුණු කඩඉම් සසඳමින්…",
  "form.aiMilestone3": "3/4 බස් සහ කාර් ගමන් කාල ගණනය කරමින්…",
  "form.aiMilestone4": "4/4 ඔබේ වෘත්තීය රුචිකත්වයන් ගළපමින්…",
  "hero.presetsTitle": "එක් ක්ලික් කිරීමකින් නියැදි ශිෂ්‍යයෙකු උත්සාහ කරන්න",
  "hero.preset1": "භෞතික විද්‍යා · 1.56 Z-ලකුණ · මහනුවර",
  "hero.preset2": "ජීව විද්‍යා · 1.42 Z-ලකුණ · ගම්පහ",
  "hero.preset3": "වාණිජ · 1.65 Z-ලකුණ · කොළඹ",
  "hero.whatIfTitle": "ප්‍රතිඵල පෙර ගවේෂකය (What-If)",
  "hero.whatIfHint": "12/13 ශ්‍රේණියේද හෝ ප්‍රතිඵල අපේක්ෂාවෙන්ද? ඉලක්ක Z-ලකුණක් තෝරා පාඨමාලා බලන්න:",
  "hero.whatIfBtn": "Z-ලකුණ {z} සමඟ පෙරදසුන",
  "shortlist.save": "සුරකින්න",
  "shortlist.saved": "සුරකින ලදී",
  "shortlist.title": "මගේ කෙටුම්පත් UGC පිළිවෙල",
  "shortlist.subtitle": "ඔබ කැමති පාඨමාලා පෙළගස්වා දෙමාපියන්ට හෝ ගුරුවරුන්ට යවන්න.",
  "shortlist.empty": "තවම පාඨමාලා සුරැක නැත. ඔබේ UGC ලැයිස්තුව සෑදීමට ඕනෑම පාඨමාලාවක 'සුරකින්න' තට්ටු කරන්න.",
  "shortlist.copyWhatsapp": "WhatsApp සඳහා පිටපත් කරන්න",
  "shortlist.copied": "පිටපත් විය!",
  "shortlist.printPdf": "මුද්‍රණය / PDF සුරකින්න",
  "shortlist.moveUp": "ඉහළට",
  "shortlist.moveDown": "පහළට",
  "shortlist.remove": "ඉවත් කරන්න",
  "share.button": "ප්‍රතිඵල බෙදාගන්න",
  "share.title": "මගේ ඉහළම රාජ්‍ය විශ්වවිද්‍යාල ගැලපීම්",
  "share.includeZscore": "කාඩ්පතේ මගේ Z-ලකුණ පෙන්වන්න",
  "share.copyText": "සාරාංශය පිටපත් කරන්න",
  "compare.button": "සසඳන්න ({count})",
  "compare.add": "සසඳන්න",
  "compare.added": "සසඳමින්",
  "compare.title": "පාඨමාලා පැති-සැසඳුම",
  "compare.clear": "හිස් කරන්න",
  "overview.zscoreGaugeTitle": "ඔබේ Z-ලකුණ එදිරිව කඩඉම් පරාසය",
  "overview.yourZscore": "ඔබේ Z-ලකුණ",
  "overview.boardingLikely": "බස් රථයෙන් ~{time} — නේවාසික පහසුකම් අවශ්‍ය විය හැක",
  "overview.commuteFeasible": "බස් රථයෙන් ~{time} — දිනපතා ගමන් කළ හැක",
  "overview.aptitudeAlert": "ක්‍රියාමාර්ගය අවශ්‍යයි: මෙම පාඨමාලාව සඳහා විශ්වවිද්‍යාල යෝග්‍යතා පරීක්ෂණයට ලියාපදිංචි වී සමත් වන්න.",
};
