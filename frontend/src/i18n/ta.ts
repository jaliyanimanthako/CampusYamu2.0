import type { Translations } from "./en.ts";

export const ta: Translations = {
  // Header
  "brand.subtitle": "உங்கள் இலங்கை அரச பல்கலைக்கழக & தொழில் வழிகாட்டி",
  "header.status.checking": "இணைக்கப்படுகிறது",
  "header.status.demo": "மாதிரி முறை",
  "header.status.offline": "இணைப்பற்றது",
  "header.status.aiReady": "AI தயார்",
  "header.status.online": "நேரடி",
  "header.editResults": "முடிவுகளைத் திருத்து",
  "header.reset": "புதியது / மீட்டமை",
  "header.shortlist": "எனது பட்டியல் ({count})",
  "header.languageLabel": "மொழி",
  "theme.light": "ஒளி",
  "theme.dark": "இருள்",
  "theme.switchToDark": "இருள் தீமுக்கு மாறு",
  "theme.switchToLight": "ஒளி தீமுக்கு மாறு",

  // App
  "app.intakeTitle": "மாணவர் விவரம் & உயர்தரப் பரீட்சை முடிவுகள்",
  "app.intakeSubtitle":
    "இலங்கை அரச பல்கலைக்கழகப் பாடநெறிகளுக்கான தகுதியைக் கண்டறிய உங்கள் உயர்தரப் பிரிவு, பாடங்கள், பொது அறிவுப் பரீட்சை மதிப்பெண் மற்றும் மாவட்டத்தை உள்ளிடவும்.",
  "app.tab.recommended": "பரிந்துரைக்கப்பட்ட வரிசை",
  "app.tab.bands": "நிலை வாரியாக அனைத்தும்",

  // ProfileForm — Loading / Offline / Demo
  "form.loadingOptions": "பிரிவுகள், பாடங்கள் மற்றும் மாவட்டங்கள் ஏற்றப்படுகின்றன…",
  "form.offlineTitle": "எங்கள் சேவையகங்கள் புதுப்பிக்கப்படுகின்றன",
  "form.offlineHint":
    "நீங்கள் இப்போது மாதிரி முடிவுகளைப் பார்க்கலாம், அல்லது சிறிது நேரத்தில் மீண்டும் முயற்சிக்கலாம்.",
  "form.retryConnection": "மீண்டும் முயற்சி",
  "form.useDemoData": "மாதிரி முடிவுகளைப் பார்",
  "form.demoBanner":
    "மாதிரி முறை: மாதிரி பல்கலைக்கழகத் தரவுடன் காட்டப்படுகிறது. இணைக்கப்பட்டதும் நேரடி முறைக்கு மாறலாம்.",
  "form.switchLiveApi": "நேரடி முறைக்கு மாறு",

  // ProfileForm — Section 1
  "form.sec1.title": "1. உயர்தரப் பிரிவு & பாடங்கள்",
  "form.sec1.subtitle":
    "உங்கள் உயர்தரப் பிரிவையும் மூன்று வெவ்வேறு பாடங்களையும் தரங்களுடன் தேர்ந்தெடுக்கவும்.",
  "form.streamLabel": "உயர்தரப் பிரிவு",
  "form.subjectSlot": "பாடம் {n}",
  "form.selectSubject": "பாடத்தைத் தேர்ந்தெடுக்கவும்…",
  "form.gradeOption": "தரம் {grade}",
  "form.softNotice.requiredAll":
    "{stream} பிரிவில் வழக்கமாக {subjects} அடங்கும். உங்கள் பாடச் சேர்க்கை சரியானதெனில் சமர்ப்பிக்கலாம்.",
  "form.softNotice.requiredAny":
    "{stream} பிரிவில் வழக்கமாக இவற்றில் ஒன்றாவது அடங்கும்: {subjects}.",
  "form.softNotice.allowed":
    "{subjects} என்பது வழக்கமான {stream} பாடத் தொகுப்புக்கு அப்பாற்பட்டது. இருப்பினும் சமர்ப்பிக்கலாம்.",

  // ProfileForm — Section 2
  "form.sec2.title": "2. பரீட்சை மதிப்பெண்கள் & சாதாரண தரத் தகுதிகள்",
  "form.cgtLabel": "பொது அறிவுப் பரீட்சை (CGT) மதிப்பெண்",
  "form.cgtPlaceholder": "0 – 100",
  "form.cgtHelp":
    "கட்டாய முழு எண் (0–100). சித்தி மதிப்பெண்ணுக்குக் குறைவாயின் எந்தப் பாடநெறிக்கும் தகுதியில்லை.",
  "form.zscoreLabel": "Z-மதிப்பெண் (Z-Score)",
  "form.optional": "(விருப்பத்தேர்வு)",
  "form.zscorePlaceholder": "உ-ம். 1.5623",
  "form.zscoreHelp":
    "Z-மதிப்பெண் இல்லாமல், தகுதியான பாடநெறிகள் 'வரலாறு இல்லை' என்பதன் கீழ் தோன்றும்.",
  "form.olToggle": "சாதாரண தரப் பெறுபேறுகள் (விருப்பத்தேர்வு — விஞ்ஞானம், ஆங்கிலம், கணிதம்)",
  "form.olSubjectLabel": "சா/த {subject}",
  "form.notSpecified": "குறிப்பிடப்படவில்லை",

  // ProfileForm — Section 3
  "form.sec3.title": "3. மாவட்டம் & வசிப்பிடம்",
  "form.sec3.subtitle":
    "பரீட்சை மாவட்டம் வெட்டுப்புள்ளிகளைத் தீர்மானிக்கும்; பயண நேரத்தைக் கணிக்க வசிக்கும் நகரம் பயன்படும்.",
  "form.admissionDistrict": "அனுமதி மாவட்டம்",
  "form.homeDistrict": "வசிக்கும் மாவட்டம்",
  "form.homeTown": "வசிக்கும் நகரம்",

  // ProfileForm — Section 4
  "form.sec4.title": "4. தொழில் & பாட ஆர்வங்கள்",
  "form.preferencesPlaceholder":
    "விருப்பத்தேர்வு: உ-ம். மென்பொருள் பொறியியல், தரவு அறிவியல், ரோபாட்டிக்ஸ், அல்லது கண்டிக்கு அருகில்",
  "form.useLlmTitle": "எனது ஆர்வங்களைப் புரிந்துகொள்ள AI ஐப் பயன்படுத்து",
  "form.useLlmHint":
    "AI முறை சிறந்த பொருத்தங்களை வழங்கும், ஆனால் பொதுவாக 20–40 வினாடிகள் எடுக்கும்.",

  // ProfileForm — Submit & Validation
  "form.sessionNote":
    "பக்கத்தைப் புதுப்பிக்கும்போது அறிக்கை இழக்கப்படாதவாறு முடிவுகள் உலாவியில் சேமிக்கப்படும்.",
  "form.analyzing": "தகுதியான பாடநெறிகள் பகுப்பாய்வு செய்யப்படுகின்றன ({seconds}s)…",
  "form.submitting": "அறிக்கை உருவாக்கப்படுகிறது…",
  "form.submit": "தகுதியான பாடநெறிகளைக் கண்டறி",
  "form.err.stream": "தயவுசெய்து ஒரு உயர்தரப் பிரிவைத் தேர்ந்தெடுக்கவும்.",
  "form.err.alAll": "தயவுசெய்து மூன்று உயர்தரப் பாடங்களையும் தேர்ந்தெடுக்கவும்.",
  "form.err.alDistinct": "தயவுசெய்து மூன்று வெவ்வேறு உயர்தரப் பாடங்களைத் தேர்ந்தெடுக்கவும்.",
  "form.err.alGrades": "ஒவ்வொரு உயர்தரப் பாடத்திற்கும் ஒரு தரத்தைத் தேர்ந்தெடுக்கவும்.",
  "form.err.cgt":
    "பொது அறிவுப் பரீட்சை (CGT) மதிப்பெண் 0 முதல் 100 வரையிலான முழு எண்ணாக இருக்க வேண்டும்.",
  "form.err.zscore": "Z-மதிப்பெண் சரியான எண்ணாக இருக்க வேண்டும் (எடுத்துக்காட்டாக, 1.5623).",
  "form.err.admissionDistrict": "தயவுசெய்து அனுமதி மாவட்டத்தைத் தேர்ந்தெடுக்கவும்.",
  "form.err.homeTown": "தயவுசெய்து உங்கள் வசிக்கும் நகரத்தைத் தேர்ந்தெடுக்கவும்.",
  "form.err.preferencesMax": "ஆர்வங்கள் 2000 எழுத்துகளுக்கு மிகாமல் இருக்க வேண்டும்.",
  "form.err.unexpected":
    "பரிந்துரைகளை உருவாக்கும்போது எதிர்பாராத பிழை ஏற்பட்டது.",

  // SummaryStrip
  "summary.noZscore": "Z-மதிப்பெண் இல்லை",
  "summary.zscorePrefix": "Z-மதிப்பெண்: {value}",
  "summary.admissionPrefix": "அனுமதி:",
  "summary.homePrefix": "வசிப்பிடம்:",
  "summary.aiInterests": "AI ஆர்வங்கள்",
  "summary.readyToApply": "விண்ணப்பிக்கத் தயார்",
  "summary.withConditions": "நிபந்தனைகளுடன்",

  // Bands
  "band.strong": "வலுவானது",
  "band.competitive": "போட்டியானது",
  "band.reach": "முயற்சிக்கலாம்",
  "band.unlikely": "வாய்ப்பு குறைவு",
  "band.no_history": "வரலாறு இல்லை",
  "band.desc.strong":
    "கடந்த ஆண்டுகளின் வெட்டுப்புள்ளிகளை உங்கள் Z-மதிப்பெண் கடந்துள்ளது.",
  "band.desc.competitive":
    "சமீபத்திய வெட்டுப்புள்ளிகளுக்கு அருகில் — அனுமதி இருபுறமும் செல்லலாம்.",
  "band.desc.reach": "சமீபத்திய வெட்டுப்புள்ளிகளை விடச் சற்றுக் குறைவு.",
  "band.desc.unlikely": "சமீபத்திய வெட்டுப்புள்ளிகளை விட மிகவும் குறைவு.",
  "band.desc.no_history":
    "தகுதியானது, ஆனால் ஒப்பிட வெட்டுப்புள்ளி வரலாறு இல்லை (அல்லது Z-மதிப்பெண் வழங்கப்படவில்லை).",

  // RankingsView
  "rankings.tab.distance": "சமநிலையான (பரிந்துரைக்கப்பட்டது)",
  "rankings.tab.preference": "ஆர்வங்களின் அடிப்படையில்",
  "rankings.tab.zscore": "அனுமதி வாய்ப்பின் அடிப்படையில்",
  "rankings.showing": "{total} இல் {shown} காட்டப்படுகிறது",
  "rankings.closeCallsToggle": "நெருக்கமான தேர்வுகள் & மாற்று ஆலோசனைகள்",
  "rankings.closeCallsTitle": "நெருக்கமான தேர்வுகள்",
  "rankings.prioritiesTitle": "முன்னுரிமை ஆலோசனைகள்",
  "rankings.empty": "இந்த விவரத்திற்கு தரவரிசைப்படுத்தப்பட்ட பாடநெறிகள் இல்லை.",
  "rankings.part.interest": "ஆர்வம்",
  "rankings.part.cutoff": "வெட்டுப்புள்ளி",
  "rankings.part.distance": "தூரம்",
  "rankings.latestCutoff": "சமீபத்திய வெட்டுப்புள்ளி",
  "rankings.travel": "பயண நேரம்",

  // BandsExplorer
  "bands.searchPlaceholder": "பாடநெறி அல்லது பல்கலைக்கழகத்தைத் தேடு…",
  "bands.searchAria": "தகுதியான பாடநெறிகளைத் தேடு",
  "bands.filter.all": "அனைத்தும்",
  "bands.filter.canApply": "விண்ணப்பிக்கத் தயார்",
  "bands.filter.withConditions": "நிபந்தனைகளுடன்",
  "bands.filter.sameDistrict": "அதே மாவட்டம்",
  "bands.empty": "உங்கள் தேடல் அல்லது வடிகட்டிக்குப் பொருந்தும் பாடநெறிகள் இல்லை.",
  "bands.badge.withConditions": "நிபந்தனைகளுடன்",
  "bands.badge.aptitudeTest": "திறனாய்வுப் பரீட்சை",
  "bands.badge.sameDistrict": "அதே மாவட்டம்",

  // CourseDrawer
  "drawer.coursePrefix": "பாடநெறி {code}",
  "drawer.closeAria": "பாடநெறி விவரங்களை மூடு",
  "drawer.tab.overview": "கண்ணோட்டம் & கையேடு",
  "drawer.tab.chat": "பாடநெறி உரையாடல்",
  "drawer.tab.career": "தொழில் வாய்ப்புகள்",

  // CourseOverview
  "overview.aptitudeRequired": "திறனாய்வுப் பரீட்சை அவசியம்",
  "overview.zscoreTitle": "Z-மதிப்பெண் & வெட்டுப்புள்ளி பகுப்பாய்வு",
  "overview.latestCutoff": "சமீபத்திய வெட்டுப்புள்ளி",
  "overview.predictedCutoff": "கணிக்கப்பட்ட வெட்டுப்புள்ளி",
  "overview.expectedMargin": "எதிர்பார்க்கப்படும் இடைவெளி",
  "overview.yearsCleared": "கடந்த ஆண்டுகள்",
  "overview.proposedIntake": "முன்மொழியப்பட்ட சேர்க்கை",
  "overview.locationTitle": "இடம், பயணம் & சா/த சரிபார்ப்புகள்",
  "overview.byCar": "காரில்",
  "overview.estBus": "மதிப்பிட்ட பேருந்து",
  "overview.roadDistance": "சாலை தூரம்",
  "overview.olMet": "சா/த {subject} பூர்த்தி",
  "overview.olFailed": "சா/த {subject} பூர்த்தியாகவில்லை",
  "overview.olUnknown": "சா/த {subject} சரிபார்க்க வேண்டும்",
  "overview.handbookTitle": "UGC கையேடு பிரிவு",

  // CourseChat
  "chat.unavailable":
    "API சேவையகத்தில் AI வசதிகள் இயக்கப்படாததால் பாடநெறி உரையாடல் தற்போது கிடைக்கவில்லை.",
  "chat.starter.1": "தொழில் வாய்ப்புகள் என்ன?",
  "chat.starter.2": "திறனாய்வுப் பரீட்சை உள்ளதா?",
  "chat.starter.3": "சாதாரண தரத் தேவைகள் என்ன?",
  "chat.emptyPrompt":
    "{university} இல் உள்ள {course} குறித்து எதையும் கேளுங்கள் — தகுதிகள், திறனாய்வுப் பரீட்சைகள், கால அளவு அல்லது தொழில் வாய்ப்புகள்.",
  "chat.role.user": "நீங்கள்",
  "chat.role.assistant": "CampusYamu ஆலோசகர்",
  "chat.sources": "ஆதாரங்கள்",
  "chat.inputPlaceholder": "இந்தப் பாடநெறி பற்றிக் கேளுங்கள்…",
  "chat.inputAria": "இந்தப் பாடநெறி பற்றி ஒரு கேள்வி கேளுங்கள்",
  "chat.send": "கேள்",
  "chat.sending": "அனுப்பப்படுகிறது…",
  "chat.failed": "உரையாடல் கோரிக்கை தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும்.",

  // CareerOutlook
  "career.checking": "{course} க்கான தொழில் வாய்ப்புகள் சரிபார்க்கப்படுகின்றன…",
  "career.loadError": "தொழில் வாய்ப்புகளை ஏற்ற முடியவில்லை.",
  "career.conflict":
    "தற்போது வேறொரு பாடநெறிக்கான ஆய்வு நடைபெறுகிறது. புதிய ஆய்வைத் தொடங்கும் முன் அது முடியும் வரை காத்திருக்கவும்.",
  "career.startError": "தொழில் ஆய்வைத் தொடங்க முடியவில்லை.",
  "career.running": "தொழில் ஆய்வு நடைபெறுகிறது…",
  "career.pollingNote": "ஒவ்வொரு 5 வினாடிகளுக்கும் புதுப்பிப்புகள் சரிபார்க்கப்படும்.",
  "career.failed": "தொழில் ஆய்வு தோல்வியடைந்தது",
  "career.title": "தொழில் வாய்ப்புகள் — {course}",
  "career.confidence": "நம்பகத்தன்மை: {value}",
  "career.sourcesCount": "பகுப்பாய்வு செய்யப்பட்ட ஆதாரங்கள்: {count}",
  "career.updated": "புதுப்பிக்கப்பட்டது: {date}",
  "career.noneTitle": "சேமிக்கப்பட்ட தொழில் ஆய்வு இன்னும் இல்லை",
  "career.availableHint":
    "இணைய தொழில் ஆய்வு {course} க்கான தற்போதைய இலங்கை வேலை வாய்ப்புகளையும் துறைசார் தேவையையும் சேகரிக்கிறது. இது பொதுவாக 3–10 நிமிடங்கள் எடுக்கும் மற்றும் ஒரு நேரத்தில் ஒரு பாடநெறிக்கு மட்டுமே இயங்கும்.",
  "career.researchBtn": "தொழில் வாய்ப்புகளை ஆய்வு செய்",
  "career.startingBtn": "ஆய்வு தொடங்கப்படுகிறது…",
  "career.unavailableHint":
    "API சேவையகத்தில் இணைய ஆய்வு விசைகள் அமைக்கப்படாததால் தொழில் ஆய்வு தற்போது கிடைக்கவில்லை.",

  // Common / Units
  "unit.min": "{n} நிமி.",
  "unit.hour": "{h}ம.",
  "unit.hourMin": "{h}ம. {m}நிமி.",
  "unit.car": "{t} கார்",
  "unit.bus": "~{t} பேருந்து",

  // Hero & Home Information
  "hero.badge": "UGC 2024/2025 மாணவர் கையேடு · இலங்கை",
  "hero.title": "உங்கள் உயர்தரப் பெறுபேறுகளுக்குப் பொருத்தமான அரச பல்கலைக்கழகப் பாடநெறியைக் கண்டறியுங்கள்.",
  "hero.subtitle":
    "மாவட்ட Z-மதிப்பெண் வெட்டுப்புள்ளிகள், உங்கள் வசிக்கும் நகரத்திலிருந்து பயண நேரம் மற்றும் தொழில் ஆர்வங்களின் அடிப்படையில் தகுதியான அனைத்துப் பட்டப்படிப்புகளையும் ஒப்பிடுங்கள்.",
  "hero.ctaPrimary": "தகுதியைச் சரிபார்க்கவும்",
  "hero.ctaSecondary": "செயல்படும் விதம்",
  "hero.stat.programmes.value": "100+",
  "hero.stat.programmes.label": "UGC பட்டப் பாடநெறிகள்",
  "hero.stat.districts.value": "25 / 489",
  "hero.stat.districts.label": "மாவட்டங்கள் & வசிக்கும் நகரங்கள்",
  "hero.stat.bands.value": "5 நிலைகள்",
  "hero.stat.bands.label": "வலுவானது முதல் வரலாறு இல்லை வரை",
  "hero.stat.languages.value": "EN · සිං · தமிழ்",
  "hero.stat.languages.label": "முழு மும்மொழி இடைமுகம்",
  "hero.previewTitle": "உங்கள் அறிக்கையில் உள்ளடங்கியவை",
  "hero.previewItem1": "கடந்த மாவட்ட வெட்டுப்புள்ளிகளின் அடிப்படையில் அனுமதி வாய்ப்பு நிலைகள்",
  "hero.previewItem2": "உங்கள் வசிக்கும் நகரத்திலிருந்து கார் & பேருந்து பயண நேர மதிப்பீடுகள்",
  "hero.previewItem3": "நேரடி UGC கையேடு மேற்கோள்கள் & பாடநெறி கேள்வி-பதில்",
  "hero.featuresTitle": "யூகமின்றி, தெளிவான தரவுகளுடன்",
  "hero.feat1.title": "Z-மதிப்பெண் & தகுதி நிலைகள்",
  "hero.feat1.desc":
    "உயர்தரப் பாட விதிகள், பொது அறிவுப் பரீட்சை மற்றும் சாதாரண தரத் தகுதிகளைச் சரிபார்த்து, பாடநெறிகளை 5 நிலைகளாகப் பிரிக்கிறது.",
  "hero.feat2.title": "சமநிலையான வரிசை & பயண நேரம்",
  "hero.feat2.desc":
    "உங்கள் ஆர்வங்கள், அனுமதி வாய்ப்பு மற்றும் வசிக்கும் நகரத்திலிருந்து பயண தூரத்தைச் சமநிலைப்படுத்தி ஆலோசனைகளை வழங்குகிறது.",
  "hero.feat3.title": "கையேடு மேற்கோள்கள் & தொழில் வாய்ப்புகள்",
  "hero.feat3.desc":
    "UGC கையேடு பிரிவுகளைப் படித்து, மேற்கோள்களுடன் AI கேள்விகள் கேட்டு, இலங்கைத் தொழில் வாய்ப்புகளை ஆய்வு செய்யுங்கள்.",
  "hero.howTitle": "3 எளிய படிகளில் செயல்படும் விதம்",
  "hero.step1.title": "பெறுபேறுகளை உள்ளிடவும்",
  "hero.step1.desc":
    "உயர்தரப் பிரிவு, 3 பாடங்கள், CGT மதிப்பெண், விருப்ப Z-மதிப்பெண் மற்றும் வசிக்கும் நகரத்தைத் தேர்ந்தெடுக்கவும்.",
  "hero.step2.title": "தரவரிசைப் பட்டியலை ஆராயுங்கள்",
  "hero.step2.desc":
    "சமநிலையான வரிசை மற்றும் நிலை வாரியான பட்டியலுக்கு இடையே மாறி மாவட்டம் அல்லது தகுதி அடிப்படையில் வடிகட்டவும்.",
  "hero.step3.title": "எந்தப் பாடநெறியையும் திறக்கவும்",
  "hero.step3.desc":
    "கையேடு விதிகள், AI உரையாடல் மற்றும் தொழில் வாய்ப்புகளுக்குப் பாடநெறிப் பலகையைத் திறக்கவும்.",
  "footer.note": "CampusYamu — UGC மாணவர் கையேடு 2024/2025 அடிப்படையில்.",

  // Wizard, Presets, What-If, Shortlist, Share & Compare
  "form.wizard.step1": "பிரிவு & பாடங்கள்",
  "form.wizard.step2": "மதிப்பெண்கள் & இடம்",
  "form.wizard.step3": "ஆர்வங்கள் & சமர்ப்பிப்பு",
  "form.wizard.next": "தொடர்க",
  "form.wizard.back": "பின்னால்",
  "form.searchDistrict": "மாவட்டத்தைத் தேடு…",
  "form.searchTown": "நகரத்தைத் தேடு…",
  "form.interestChipsLabel": "விரைவு ஆர்வக் குறிச்சொற்கள் (சேர்க்கத் தட்டவும்):",
  "form.aiMilestone1": "1/4 UGC தகுதி விதிகள் சரிபார்க்கப்படுகின்றன…",
  "form.aiMilestone2": "2/4 25 மாவட்ட Z-மதிப்பெண் வெட்டுப்புள்ளிகள் ஒப்பிடப்படுகின்றன…",
  "form.aiMilestone3": "3/4 பேருந்து & கார் பயண நேரங்கள் கணக்கிடப்படுகின்றன…",
  "form.aiMilestone4": "4/4 உங்கள் தொழில் ஆர்வங்கள் பொருத்தப்படுகின்றன…",
  "hero.presetsTitle": "ஒரு கிளிக்கில் மாதிரி மாணவரை முயற்சிக்கவும்",
  "hero.preset1": "பௌதிக விஞ்ஞானம் · 1.56 Z-மதிப்பெண் · கண்டி",
  "hero.preset2": "உயிரியல் விஞ்ஞானம் · 1.42 Z-மதிப்பெண் · கம்பஹா",
  "hero.preset3": "வணிகம் · 1.65 Z-மதிப்பெண் · கொழும்பு",
  "hero.whatIfTitle": "முடிவுகளுக்கு முந்தைய What-If முன்னோட்டம்",
  "hero.whatIfHint": "தரம் 12/13 மாணவரா? இலக்கு Z-மதிப்பெண்ணை நகர்த்திப் பாடநெறிகளைப் பாருங்கள்:",
  "hero.whatIfBtn": "{z} Z-மதிப்பெண்ணுடன் முன்னோட்டம்",
  "shortlist.save": "சேமி",
  "shortlist.saved": "சேமிக்கப்பட்டது",
  "shortlist.title": "எனது UGC வரைவுப் பட்டியல்",
  "shortlist.subtitle": "விரும்பிய பாடநெறிகளை வரிசைப்படுத்தி பெற்றோர் அல்லது ஆசிரியர்களுக்கு அனுப்பவும்.",
  "shortlist.empty": "இதுவரை பாடநெறிகள் சேமிக்கப்படவில்லை. உங்கள் UGC பட்டியலை உருவாக்க 'சேமி' என்பதைத் தட்டவும்.",
  "shortlist.copyWhatsapp": "WhatsApp க்கு நகலெடு",
  "shortlist.copied": "நகலெடுக்கப்பட்டது!",
  "shortlist.printPdf": "அச்சிடு / PDF சேமி",
  "shortlist.moveUp": "மேலே நகர்த்து",
  "shortlist.moveDown": "கீழே நகர்த்து",
  "shortlist.remove": "அகற்று",
  "share.button": "சிறந்த பொருத்தங்களைப் பகிர்",
  "share.title": "எனது சிறந்த அரச பல்கலைக்கழகப் பொருத்தங்கள்",
  "share.includeZscore": "அட்டையில் எனது Z-மதிப்பெண்ணைக் காட்டு",
  "share.copyText": "சுருக்கத்தை நகலெடு",
  "compare.button": "ஒப்பிடு ({count})",
  "compare.add": "ஒப்பிடு",
  "compare.added": "ஒப்பிடப்படுகிறது",
  "compare.title": "பாடநெறிகள் பக்கவாட்டு ஒப்பீடு",
  "compare.clear": "அழி",
  "overview.zscoreGaugeTitle": "உங்கள் Z-மதிப்பெண் vs வெட்டுப்புள்ளி வரம்பு",
  "overview.yourZscore": "உங்கள் Z-மதிப்பெண்",
  "overview.boardingLikely": "பேருந்தில் ~{time} — தங்குமிடம் தேவைப்படலாம்",
  "overview.commuteFeasible": "பேருந்தில் ~{time} — தினசரி பயணம் சாத்தியம்",
  "overview.aptitudeAlert": "செயல் தேவை: இந்தப் பாடநெறிக்கான பல்கலைக்கழக திறனாய்வுப் பரீட்சைக்குப் பதிவு செய்து சித்தி பெறவும்.",
};
