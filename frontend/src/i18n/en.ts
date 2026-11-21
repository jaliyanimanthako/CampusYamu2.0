export const en = {
  // Header
  "brand.subtitle": "Your Sri Lankan State University & Career Compass",
  "header.status.checking": "Connecting",
  "header.status.demo": "Sample Mode",
  "header.status.offline": "Offline",
  "header.status.aiReady": "AI Ready",
  "header.status.online": "Live",
  "header.editResults": "Edit Results",
  "header.reset": "New / Reset",
  "header.shortlist": "My UGC List ({count})",
  "header.languageLabel": "Language",
  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.switchToDark": "Switch to dark theme",
  "theme.switchToLight": "Switch to light theme",

  // App
  "app.intakeTitle": "Student Profile & A/L Results",
  "app.intakeSubtitle":
    "Enter your A/L stream, subjects, Common General Test mark, and district to find eligible Sri Lankan state-university courses.",
  "app.tab.recommended": "Recommended Order",
  "app.tab.bands": "All Eligible by Band",

  // ProfileForm — Loading / Offline / Demo
  "form.loadingOptions": "Loading streams, subjects, and districts…",
  "form.offlineTitle": "We're refreshing our servers",
  "form.offlineHint":
    "Explore sample results right now, or try connecting again in a moment.",
  "form.retryConnection": "Retry",
  "form.useDemoData": "Explore Sample Results",
  "form.demoBanner":
    "Sample Mode: Exploring with demo university data. Switch to Live Mode anytime when connected.",
  "form.switchLiveApi": "Switch to Live Mode",

  // ProfileForm — Section 1
  "form.sec1.title": "1. A/L Stream & Subjects",
  "form.sec1.subtitle":
    "Select your A/L stream and three distinct A/L subjects with grades.",
  "form.streamLabel": "A/L Stream",
  "form.subjectSlot": "Subject {n}",
  "form.selectSubject": "Select subject…",
  "form.gradeOption": "Grade {grade}",
  "form.softNotice.requiredAll":
    "{stream} usually includes {subjects}. You can still submit if your combination is valid.",
  "form.softNotice.requiredAny":
    "{stream} usually includes at least one of: {subjects}.",
  "form.softNotice.allowed":
    "{subjects} is outside the typical {stream} subject set. Submission is still allowed.",

  // ProfileForm — Section 2
  "form.sec2.title": "2. Exam Marks & O/L Prerequisites",
  "form.cgtLabel": "Common General Test (CGT) Mark",
  "form.cgtPlaceholder": "0 – 100",
  "form.cgtHelp":
    "Required integer (0–100). Below the pass mark, no courses are eligible.",
  "form.zscoreLabel": "Z-Score",
  "form.optional": "(Optional)",
  "form.zscorePlaceholder": "e.g. 1.5623",
  "form.zscoreHelp":
    "Without a Z-score, eligible courses appear under No History.",
  "form.olToggle": "O/L Grades (Optional — Science, English, Mathematics)",
  "form.olSubjectLabel": "O/L {subject}",
  "form.notSpecified": "Not specified",

  // ProfileForm — Section 3
  "form.sec3.title": "3. District & Home Location",
  "form.sec3.subtitle":
    "Admission district determines Z-score cut-offs; home town is used for travel time estimates.",
  "form.admissionDistrict": "Admission District",
  "form.homeDistrict": "Home District",
  "form.homeTown": "Home Town",

  // ProfileForm — Section 4
  "form.sec4.title": "4. Career & Subject Interests",
  "form.preferencesPlaceholder":
    "Optional: e.g. software engineering, data science, robotics, or working close to Kandy",
  "form.useLlmTitle": "Use AI to interpret my interests",
  "form.useLlmHint":
    "AI mode provides deeper preference matching, but typically takes 20–40 seconds.",

  // ProfileForm — Submit & Validation
  "form.sessionNote":
    "Results are saved in your browser session so refreshes do not lose your report.",
  "form.analyzing": "Analyzing eligible courses ({seconds}s)…",
  "form.submitting": "Generating Report…",
  "form.submit": "Find Eligible Courses",
  "form.err.stream": "Please select an A/L stream.",
  "form.err.alAll": "Please select all three A/L subjects.",
  "form.err.alDistinct": "Please choose three different A/L subjects.",
  "form.err.alGrades": "Please select a grade for each A/L subject.",
  "form.err.cgt":
    "Common General Test (CGT) mark must be an integer between 0 and 100.",
  "form.err.zscore": "Z-score must be a valid number (for example, 1.5623).",
  "form.err.admissionDistrict": "Please select an admission district.",
  "form.err.homeTown": "Please select your home town.",
  "form.err.preferencesMax": "Interests must be 2000 characters or fewer.",
  "form.err.unexpected":
    "An unexpected error occurred while generating recommendations.",

  // SummaryStrip
  "summary.noZscore": "No Z-score",
  "summary.zscorePrefix": "Z-score: {value}",
  "summary.admissionPrefix": "Admission:",
  "summary.homePrefix": "Home:",
  "summary.aiInterests": "AI Interests",
  "summary.readyToApply": "Ready to Apply",
  "summary.withConditions": "With Conditions",

  // Bands
  "band.strong": "Strong",
  "band.competitive": "Competitive",
  "band.reach": "Reach",
  "band.unlikely": "Unlikely",
  "band.no_history": "No History",
  "band.desc.strong":
    "Your Z-score has cleared this course's cut-off in past years.",
  "band.desc.competitive":
    "Close to recent cut-offs — admission could go either way.",
  "band.desc.reach": "Somewhat below recent cut-offs.",
  "band.desc.unlikely": "Well below recent cut-offs.",
  "band.desc.no_history":
    "Eligible, with no cut-off history to compare (or no Z-score given).",

  // RankingsView
  "rankings.tab.distance": "Balanced (Recommended)",
  "rankings.tab.preference": "By Interests",
  "rankings.tab.zscore": "By Admission Chance",
  "rankings.showing": "Showing {shown} of {total}",
  "rankings.closeCallsToggle": "Close Calls & What-If Advice",
  "rankings.closeCallsTitle": "Close Calls",
  "rankings.prioritiesTitle": "What-If Priorities",
  "rankings.empty": "No ranked courses available for this profile.",
  "rankings.part.interest": "Interest",
  "rankings.part.cutoff": "Cut-off",
  "rankings.part.distance": "Distance",
  "rankings.latestCutoff": "Latest Cut-off",
  "rankings.travel": "Travel",

  // BandsExplorer
  "bands.searchPlaceholder": "Search course or university…",
  "bands.searchAria": "Search eligible courses",
  "bands.filter.all": "All",
  "bands.filter.canApply": "Ready to Apply",
  "bands.filter.withConditions": "With Conditions",
  "bands.filter.sameDistrict": "Same District",
  "bands.empty": "No eligible courses match your current search or filter.",
  "bands.badge.withConditions": "With conditions",
  "bands.badge.aptitudeTest": "Aptitude test",
  "bands.badge.sameDistrict": "Same district",

  // CourseDrawer
  "drawer.coursePrefix": "Course {code}",
  "drawer.closeAria": "Close course drawer",
  "drawer.tab.overview": "Overview & Handbook",
  "drawer.tab.chat": "Course Chat",
  "drawer.tab.career": "Career Outlook",

  // CourseOverview
  "overview.aptitudeRequired": "Aptitude Test Required",
  "overview.zscoreTitle": "Z-Score & Cut-off Analysis",
  "overview.latestCutoff": "Latest Cut-off",
  "overview.predictedCutoff": "Predicted Cut-off",
  "overview.expectedMargin": "Expected Margin",
  "overview.yearsCleared": "Years Cleared",
  "overview.proposedIntake": "Proposed Intake",
  "overview.locationTitle": "Location, Travel & O/L Checks",
  "overview.byCar": "By Car",
  "overview.estBus": "Est. Bus",
  "overview.roadDistance": "Road Distance",
  "overview.olMet": "O/L {subject} met",
  "overview.olFailed": "O/L {subject} not met",
  "overview.olUnknown": "O/L {subject} to verify",
  "overview.handbookTitle": "UGC Handbook Section",

  // CourseChat
  "chat.unavailable":
    "Course chat is currently unavailable because AI features are not enabled on the API server.",
  "chat.starter.1": "What are the career prospects?",
  "chat.starter.2": "Is there an aptitude test?",
  "chat.starter.3": "What are the O/L requirements?",
  "chat.emptyPrompt":
    "Ask any question about {course} at {university} — requirements, aptitude tests, duration, or career prospects.",
  "chat.role.user": "You",
  "chat.role.assistant": "CampusYamu Advisor",
  "chat.sources": "Sources",
  "chat.inputPlaceholder": "Ask about this course…",
  "chat.inputAria": "Ask a question about this course",
  "chat.send": "Ask",
  "chat.sending": "Sending…",
  "chat.failed": "Chat request failed. Please try again.",

  // CareerOutlook
  "career.checking": "Checking career outlook for {course}…",
  "career.loadError": "Unable to load career outlook.",
  "career.conflict":
    "Another course is currently being researched. Please wait for it to finish before starting a new research job.",
  "career.startError": "Failed to start career research.",
  "career.running": "Career research in progress…",
  "career.pollingNote": "Checking for updates every 5 seconds.",
  "career.failed": "Career research failed",
  "career.title": "Career Outlook — {course}",
  "career.confidence": "Confidence: {value}",
  "career.sourcesCount": "Sources analyzed: {count}",
  "career.updated": "Updated: {date}",
  "career.noneTitle": "No Cached Career Research Yet",
  "career.availableHint":
    "Web career research gathers current Sri Lankan job prospects and industry demand for {course}. Research typically takes 3–10 minutes and runs one course at a time.",
  "career.researchBtn": "Research Career Prospects",
  "career.startingBtn": "Starting Research…",
  "career.unavailableHint":
    "Career research is currently unavailable because web research keys are not configured on the API server.",

  // Common / Units
  "unit.min": "{n} min",
  "unit.hour": "{h}h",
  "unit.hourMin": "{h}h {m}m",
  "unit.car": "{t} car",
  "unit.bus": "~{t} bus",

  // Hero & Home Information
  "hero.badge": "UGC 2024/2025 Student Handbook · Sri Lanka",
  "hero.title": "Find the right state-university course for your A/L results.",
  "hero.subtitle":
    "Compare every eligible degree across Sri Lankan state universities by historical district Z-score cut-offs, travel time from your home town, and your career interests.",
  "hero.ctaPrimary": "Check Your Eligibility",
  "hero.ctaSecondary": "How It Works",
  "hero.stat.programmes.value": "100+",
  "hero.stat.programmes.label": "UGC degree programmes",
  "hero.stat.districts.value": "25 / 489",
  "hero.stat.districts.label": "Districts & home towns",
  "hero.stat.bands.value": "5 Bands",
  "hero.stat.bands.label": "Strong to No History",
  "hero.stat.languages.value": "EN · සිං · தமிழ்",
  "hero.stat.languages.label": "Full trilingual interface",
  "hero.previewTitle": "What your report includes",
  "hero.previewItem1": "Admission likelihood bands from past district cut-offs",
  "hero.previewItem2": "Car & bus travel estimates from your home town",
  "hero.previewItem3": "Direct UGC handbook citations & course Q&A",
  "hero.featuresTitle": "Built for clarity, not guesswork",
  "hero.feat1.title": "Z-Score & Eligibility Bands",
  "hero.feat1.desc":
    "Automatically checks A/L subject rules, Common General Test pass mark, and O/L prerequisites, then groups courses into Strong, Competitive, Reach, Unlikely, and No History.",
  "hero.feat2.title": "Balanced Order & Travel Time",
  "hero.feat2.desc":
    "Balances your stated interests, admission certainty, and estimated car or bus commute from your home town—with close-call and what-if advice.",
  "hero.feat3.title": "Handbook Citations & Career Outlook",
  "hero.feat3.desc":
    "Inspect exact UGC handbook sections in Markdown, ask course-specific AI questions with citations, and check researched Sri Lankan career prospects.",
  "hero.howTitle": "How it works in 3 steps",
  "hero.step1.title": "Enter your results",
  "hero.step1.desc":
    "Pick your A/L stream, 3 subjects, CGT mark, optional Z-score, and home town.",
  "hero.step2.title": "Explore ranked matches",
  "hero.step2.desc":
    "Switch between Balanced Order and Band Explorer to filter by readiness or district.",
  "hero.step3.title": "Inspect any course",
  "hero.step3.desc":
    "Open the slide-over drawer for handbook rules, AI Q&A, and career outlook.",
  "footer.note": "CampusYamu — Based on UGC Student Handbook 2024/2025.",

  // Wizard, Presets, What-If, Shortlist, Share & Compare
  "form.wizard.step1": "Stream & Subjects",
  "form.wizard.step2": "Marks & Location",
  "form.wizard.step3": "Interests & Submit",
  "form.wizard.next": "Continue",
  "form.wizard.back": "Back",
  "form.searchDistrict": "Filter districts…",
  "form.searchTown": "Filter towns…",
  "form.interestChipsLabel": "Quick interest tags (tap to add):",
  "form.aiMilestone1": "1/4 Checking UGC eligibility rules…",
  "form.aiMilestone2": "2/4 Comparing 25-district Z-score cut-offs…",
  "form.aiMilestone3": "3/4 Calculating bus & car travel times…",
  "form.aiMilestone4": "4/4 Matching your career interests…",
  "hero.presetsTitle": "Try a sample student in 1 click",
  "hero.preset1": "Physical Science · 1.56 Z-Score · Kandy",
  "hero.preset2": "Biological Science · 1.42 Z-Score · Gampaha",
  "hero.preset3": "Commerce · 1.65 Z-Score · Colombo",
  "hero.whatIfTitle": "Pre-Results What-If Explorer",
  "hero.whatIfHint": "In Year 12/13 or awaiting results? Slide a target Z-score to preview courses:",
  "hero.whatIfBtn": "Preview with {z} Z-Score",
  "shortlist.save": "Save",
  "shortlist.saved": "Saved",
  "shortlist.title": "My Draft UGC Order",
  "shortlist.subtitle": "Reorder your preferred courses and export for parents, teachers, or your UGC application.",
  "shortlist.empty": "No courses saved yet. Tap Save on any course card to build your UGC preference list.",
  "shortlist.copyWhatsapp": "Copy for WhatsApp",
  "shortlist.copied": "Copied!",
  "shortlist.printPdf": "Print / Save PDF",
  "shortlist.moveUp": "Move up",
  "shortlist.moveDown": "Move down",
  "shortlist.remove": "Remove",
  "share.button": "Share Top Matches",
  "share.title": "My Top State University Matches",
  "share.includeZscore": "Include my Z-score on card",
  "share.copyText": "Copy Summary",
  "compare.button": "Compare ({count})",
  "compare.add": "Compare",
  "compare.added": "Comparing",
  "compare.title": "Side-by-Side Course Comparison",
  "compare.clear": "Clear",
  "overview.zscoreGaugeTitle": "Your Z-Score vs. Cut-off Range",
  "overview.yourZscore": "Your Z-Score",
  "overview.boardingLikely": "~{time} by bus — Boarding likely needed",
  "overview.commuteFeasible": "~{time} by bus — Daily commute feasible",
  "overview.aptitudeAlert": "Action required: Register for and pass the university Aptitude Test for this programme.",
} as const;

export type TranslationKey = keyof typeof en;
export type Translations = Record<TranslationKey, string>;
