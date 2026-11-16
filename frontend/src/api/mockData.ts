import type {
  CareerResearchResponse,
  CareerStatus,
  ChatRequest,
  ChatResponse,
  CourseRow,
  Options,
  RecommendationReport,
  RecommendationRequest,
  RecommendationResponse,
} from "./types.ts";

const ALL_DISTRICTS: string[] = [
  "Ampara",
  "Anuradhapura",
  "Badulla",
  "Batticaloa",
  "Colombo",
  "Galle",
  "Gampaha",
  "Hambantota",
  "Jaffna",
  "Kalutara",
  "Kandy",
  "Kegalle",
  "Kilinochchi",
  "Kurunegala",
  "Mannar",
  "Matale",
  "Matara",
  "Monaragala",
  "Mullaitivu",
  "Nuwara Eliya",
  "Polonnaruwa",
  "Puttalam",
  "Ratnapura",
  "Trincomalee",
  "Vavuniya",
];

const DS_DIVISIONS: Record<string, string[]> = {
  Ampara: ["Ampara", "Kalmunai", "Akkaraipattu", "Samanthurai", "Uhana"],
  Anuradhapura: ["Nuwaragam Palatha East", "Nuwaragam Palatha Central", "Kekirawa", "Mihintale"],
  Badulla: ["Badulla", "Bandarawela", "Hali-Ela", "Passara", "Welimada"],
  Batticaloa: ["Manmunai North", "Kattankudy", "Eravur Pattu", "Koralai Pattu"],
  Colombo: ["Colombo", "Thimbirigasyaya", "Dehiwala", "Kaduwela", "Maharagama", "Moratuwa"],
  Galle: ["Galle Four Gravets", "Akmeemana", "Ambalangoda", "Hikkaduwa", "Elpitiya"],
  Gampaha: ["Gampaha", "Negombo", "Kelaniya", "Wattala", "Ja-Ela", "Minuwangoda"],
  Hambantota: ["Hambantota", "Tangalle", "Tissamaharama", "Beliatta"],
  Jaffna: ["Jaffna", "Nallur", "Valikamam South", "Chavakachcheri"],
  Kalutara: ["Kalutara", "Panadura", "Horana", "Beruwala", "Bandaragama"],
  Kandy: [
    "Gangawata Korale",
    "Akurana",
    "Deltota",
    "Doluwa",
    "Harispattuwa",
    "Kundasale",
    "Pathadumbara",
    "Yatinuwara",
  ],
  Kegalle: ["Kegalle", "Mawanella", "Rambukkana", "Warakapola"],
  Kilinochchi: ["Karachchi", "Kandavalai", "Pachchilaipalli"],
  Kurunegala: ["Kurunegala", "Kuliyapitiya East", "Pannala", "Polgahawela", "Wariyapola"],
  Mannar: ["Mannar Town", "Nanaddan", "Musali"],
  Matale: ["Matale", "Dambulla", "Galewela", "Ukuwela"],
  Matara: ["Matara Four Gravets", "Weligama", "Akuressa", "Devinuwara"],
  Monaragala: ["Monaragala", "Wellawaya", "Bibile", "Buttala"],
  Mullaitivu: ["Maritimepattu", "Puthukkudiyiruppu", "Oddusuddan"],
  "Nuwara Eliya": ["Nuwara Eliya", "Ambagamuwa", "Kothmale", "Walapane"],
  Polonnaruwa: ["Thamankaduwa", "Hingurakgoda", "Medirigiriya"],
  Puttalam: ["Puttalam", "Chilaw", "Wennappuwa", "Nattandiya"],
  Ratnapura: ["Ratnapura", "Balangoda", "Embilipitiya", "Pelmadulla"],
  Trincomalee: ["Trincomalee Town and Gravets", "Kinniya", "Kantale"],
  Vavuniya: ["Vavuniya", "Vavuniya South", "Vengalacheddikulam"],
};

export const MOCK_OPTIONS: Options = {
  streams: [
    "Arts",
    "Commerce",
    "Biological Science",
    "Physical Science",
    "Engineering Technology",
    "Biosystems Technology",
    "Information Communication Technology",
  ],
  stream_hints: {
    "Physical Science": {
      defaults: ["Combined Mathematics", "Physics", "Chemistry"],
      allowed: [
        "Combined Mathematics",
        "Physics",
        "Chemistry",
        "Information & Communication Technology",
      ],
      required_all: ["Combined Mathematics", "Physics"],
      source: "owner stream_subjects",
    },
    "Biological Science": {
      defaults: ["Biology", "Chemistry", "Physics"],
      allowed: ["Biology", "Chemistry", "Physics", "Agricultural Science"],
      required_all: ["Biology", "Chemistry"],
      source: "owner stream_subjects",
    },
    Commerce: {
      defaults: ["Accounting", "Business Studies", "Economics"],
      required_any: ["Accounting", "Business Studies", "Economics"],
      source: "form hint",
    },
    "Engineering Technology": {
      defaults: [
        "Engineering Technology",
        "Science for Technology",
        "Information & Communication Technology",
      ],
      required_all: ["Engineering Technology", "Science for Technology"],
      source: "form hint",
    },
    "Biosystems Technology": {
      defaults: [
        "Biosystems Technology",
        "Science for Technology",
        "Agricultural Science",
      ],
      required_all: ["Biosystems Technology", "Science for Technology"],
      source: "form hint",
    },
    "Information Communication Technology": {
      defaults: [
        "Information & Communication Technology",
        "Combined Mathematics",
        "Physics",
      ],
      required_all: ["Information & Communication Technology"],
      source: "form hint",
    },
    Arts: {
      defaults: [],
      source: "form hint",
    },
  },
  al_subjects: [
    "Accounting",
    "Agricultural Science",
    "Agro Technology",
    "Arabic",
    "Art",
    "Biology",
    "Biosystems Technology",
    "Buddhism",
    "Buddhist Civilization",
    "Business Statistics",
    "Business Studies",
    "Chemistry",
    "Combined Mathematics",
    "Communication & Media Studies",
    "Dancing",
    "Drama & Theatre",
    "Economics",
    "Engineering Technology",
    "English",
    "French",
    "Geography",
    "Greek & Roman Civilization",
    "Higher Mathematics",
    "Hindu Civilization",
    "Hinduism",
    "History",
    "Home Economics",
    "Information & Communication Technology",
    "Islam",
    "Islamic Civilization",
    "Logic & Scientific Method",
    "Mathematics",
    "Music",
    "Pali",
    "Physics",
    "Political Science",
    "Sanskrit",
    "Science for Technology",
    "Sinhala",
    "Tamil",
  ],
  al_grades: ["A", "B", "C", "S", "F"],
  ol_subjects: ["Science", "English", "Mathematics"],
  ol_grades: ["A", "B", "C", "S", "W"],
  districts: ALL_DISTRICTS,
  ds_divisions: DS_DIVISIONS,
  llm_available: true,
};

function makeCourseRow(partial: Partial<CourseRow> & Pick<CourseRow, "uni_code" | "course_code" | "course_name" | "university" | "band">): CourseRow {
  return {
    site: partial.university,
    site_district: "Colombo",
    group: "can_apply",
    aptitude_test: false,
    ol_met: ["Mathematics", "English"],
    ol_failed: [],
    ol_unknown: [],
    proposed_intake: 180,
    latest_year: "2024_2025",
    car_min: 45,
    bus_min_est: 75,
    road_km: 32.5,
    same_district: false,
    preference_score: 2,
    details_block: 0,
    ...partial,
  };
}

export function buildMockRecommendationResponse(
  req: RecommendationRequest,
): RecommendationResponse {
  const hasZ = typeof req.z_score === "number" && !Number.isNaN(req.z_score);
  const z = hasZ ? (req.z_score as number) : null;
  const cgtPassed = req.cgt >= 30;

  const sampleRows: CourseRow[] = cgtPassed
    ? [
        makeCourseRow({
          uni_code: "013B",
          course_code: "013",
          course_name: "Physical Science",
          university: "University of Peradeniya",
          site: "Peradeniya",
          site_district: "Kandy",
          band: hasZ ? (z! >= 1.3 ? "strong" : "competitive") : "no_history",
          proposed_intake: 280,
          latest_cutoff: hasZ ? 1.2874 : null,
          predicted_cutoff: hasZ ? 1.2678 : null,
          uncertainty: hasZ ? 0.1088 : null,
          expected_margin: hasZ ? Number((z! - 1.2678).toFixed(4)) : null,
          years_met: hasZ ? 5 : null,
          years_compared: hasZ ? 6 : null,
          car_min: req.admission_district === "Kandy" ? 12.4 : 95.0,
          bus_min_est: req.admission_district === "Kandy" ? 28.0 : 145.0,
          road_km: req.admission_district === "Kandy" ? 7.2 : 98.4,
          same_district: req.admission_district === "Kandy",
          preference_score: 4,
          reason: hasZ
            ? "Your Z-score clears the recent cut-off trend for this programme in your admission district."
            : undefined,
          zscore_note: hasZ ? undefined : "No Z-score provided; eligibility verified without cut-off ranking.",
        }),
        makeCourseRow({
          uni_code: "019A",
          course_code: "019",
          course_name: "Computer Science",
          university: "University of Colombo",
          site: "Colombo 07",
          site_district: "Colombo",
          band: hasZ ? (z! >= 1.7 ? "strong" : z! >= 1.45 ? "competitive" : "reach") : "no_history",
          proposed_intake: 160,
          latest_cutoff: hasZ ? 1.5912 : null,
          predicted_cutoff: hasZ ? 1.605 : null,
          uncertainty: hasZ ? 0.082 : null,
          expected_margin: hasZ ? Number((z! - 1.605).toFixed(4)) : null,
          years_met: hasZ ? 3 : null,
          years_compared: hasZ ? 6 : null,
          car_min: req.admission_district === "Colombo" ? 18.0 : 122.0,
          bus_min_est: req.admission_district === "Colombo" ? 35.0 : 185.0,
          road_km: req.admission_district === "Colombo" ? 9.5 : 115.2,
          same_district: req.admission_district === "Colombo",
          preference_score: 5,
          reason: hasZ
            ? "Close to recent cut-offs; outcome depends on district intake shifts."
            : undefined,
          zscore_note: hasZ ? undefined : "No Z-score provided; eligibility verified without cut-off ranking.",
        }),
        makeCourseRow({
          uni_code: "022K",
          course_code: "022",
          course_name: "Information Technology",
          university: "University of Moratuwa",
          site: "Katubedda",
          site_district: "Colombo",
          band: hasZ ? (z! >= 1.6 ? "strong" : z! >= 1.35 ? "competitive" : "reach") : "no_history",
          group: "with_conditions",
          aptitude_test: true,
          ol_met: ["Mathematics", "English"],
          proposed_intake: 120,
          latest_cutoff: hasZ ? 1.482 : null,
          predicted_cutoff: hasZ ? 1.495 : null,
          uncertainty: hasZ ? 0.075 : null,
          expected_margin: hasZ ? Number((z! - 1.495).toFixed(4)) : null,
          years_met: hasZ ? 4 : null,
          years_compared: hasZ ? 6 : null,
          car_min: req.admission_district === "Colombo" ? 28.0 : 134.0,
          bus_min_est: req.admission_district === "Colombo" ? 50.0 : 198.0,
          road_km: req.admission_district === "Colombo" ? 16.0 : 126.4,
          same_district: req.admission_district === "Colombo",
          preference_score: 5,
          reason: hasZ
            ? "Requires passing an aptitude test in addition to the Z-score cut-off."
            : undefined,
          zscore_note: hasZ ? undefined : "No Z-score provided; eligibility verified without cut-off ranking.",
        }),
        makeCourseRow({
          uni_code: "008A",
          course_code: "008",
          course_name: "Engineering",
          university: "University of Moratuwa",
          site: "Katubedda",
          site_district: "Colombo",
          band: hasZ ? (z! >= 1.85 ? "strong" : z! >= 1.6 ? "reach" : "unlikely") : "no_history",
          group: "with_conditions",
          ol_met: ["Mathematics", "Science"],
          ol_unknown: req.ol && req.ol.length > 0 ? [] : ["English"],
          proposed_intake: 850,
          latest_cutoff: hasZ ? 1.7921 : null,
          predicted_cutoff: hasZ ? 1.81 : null,
          uncertainty: hasZ ? 0.065 : null,
          expected_margin: hasZ ? Number((z! - 1.81).toFixed(4)) : null,
          years_met: hasZ ? 1 : null,
          years_compared: hasZ ? 6 : null,
          car_min: 138.0,
          bus_min_est: 205.0,
          road_km: 129.0,
          same_district: false,
          preference_score: 5,
          reason: hasZ
            ? "Competitive national engineering intake; recent cut-offs sit above your current Z-score."
            : undefined,
          zscore_note: hasZ ? undefined : "No Z-score provided; eligibility verified without cut-off ranking.",
        }),
        makeCourseRow({
          uni_code: "105D",
          course_code: "105",
          course_name: "Data Science & Analytics",
          university: "Sabaragamuwa University of Sri Lanka",
          site: "Belihuloya",
          site_district: "Ratnapura",
          band: "no_history",
          proposed_intake: 60,
          latest_cutoff: null,
          predicted_cutoff: null,
          car_min: 112.0,
          bus_min_est: 170.0,
          road_km: 102.0,
          same_district: req.admission_district === "Ratnapura",
          preference_score: 4,
          zscore_note: "New intake programme without 3-year district cut-off history.",
        }),
      ]
    : [];

  const bands: RecommendationReport["bands"] = {
    strong: sampleRows.filter((r) => r.band === "strong"),
    competitive: sampleRows.filter((r) => r.band === "competitive"),
    reach: sampleRows.filter((r) => r.band === "reach"),
    unlikely: sampleRows.filter((r) => r.band === "unlikely"),
    no_history: sampleRows.filter((r) => r.band === "no_history"),
  };

  const suggestions = sampleRows.map((row, idx) => ({
    position: idx + 1,
    uni_code: row.uni_code,
    course_code: row.course_code,
    course_name: row.course_name,
    university: row.university,
    band: row.band,
    latest_cutoff: row.latest_cutoff,
    car_min: row.car_min,
    bus_min_est: row.bus_min_est,
    preference_score: row.preference_score,
    flags: row.aptitude_test ? ["aptitude test"] : [],
    combined_score: Number((0.85 - idx * 0.08).toFixed(2)),
    parts: {
      interest: 0.42 - idx * 0.04,
      cutoff: hasZ ? 0.32 - idx * 0.05 : 0.2,
      distance: 0.26 - idx * 0.03,
    },
  }));

  const report: RecommendationReport = {
    profile: {
      stream: req.stream,
      al_results: req.al.map((item) => [item.subject, item.grade || ""]),
      common_general_test: req.cgt,
      admission_district: req.admission_district,
      home: req.ds_division,
      ol_results: (req.ol || []).map((item) => [item.subject, item.grade || ""]),
      z_score: z,
    },
    origin: {
      ds_division: req.ds_division,
      district: req.admission_district,
      province: "Demo Province",
    },
    counts: {
      can_apply: sampleRows.filter((r) => r.group === "can_apply").length,
      with_conditions: sampleRows.filter((r) => r.group === "with_conditions").length,
      not_eligible: cgtPassed ? 18 : 112,
      band_strong: bands.strong.length,
      band_competitive: bands.competitive.length,
      band_reach: bands.reach.length,
      band_unlikely: bands.unlikely.length,
      band_no_history: bands.no_history.length,
    },
    bands,
    rankings: {
      distance: {
        title: "Balanced Order (Interests, Cut-off & Travel Time)",
        total: suggestions.length,
        suggestions,
        feedback: {
          summary: cgtPassed
            ? "Demo report generated locally. Connect to the FastAPI backend (make api) for full UGC 2024/2025 handbook analysis across all 100+ programmes."
            : "Common General Test mark is below the pass threshold (30), so no courses are eligible.",
          course_notes: cgtPassed
            ? {
                "013B": {
                  note: "Strong admission margin combined with short travel distance.",
                },
                "022K": {
                  note: "High interest match; remember to register for the aptitude test.",
                },
              }
            : {},
          close_calls: cgtPassed
            ? [
                {
                  ranks: "Ranks 2 & 3",
                  note: "Computer Science (Colombo) and Information Technology (Moratuwa) are nearly tied in combined score.",
                },
              ]
            : [],
          priorities: cgtPassed
            ? [
                {
                  label: "If staying close to home matters most",
                  advice: "Keep Physical Science (Peradeniya) at #1 for minimal daily commute.",
                },
                {
                  label: "If maximizing admission certainty matters most",
                  advice: "Order Strong band courses above Competitive and Reach options.",
                },
              ]
            : [],
        },
      },
      preference: {
        title: "Ordered by Interests & Competitiveness",
        total: suggestions.length,
        suggestions,
      },
      zscore: {
        title: "Ordered by Admission Chance",
        total: suggestions.length,
        suggestions,
      },
    },
    preferences: {
      text: req.preferences || "",
    },
    course_details: {
      "013": {
        course_name: "Physical Science",
        blocks: [
          {
            title: "Physical Science",
            section: "2.2.4.5",
            pages: [78],
            citation: "Handbook §2.2.4.5, p. 78",
            degree_programmes: ["Bachelor of Science in Physical Science"],
            duration: ["3 Years / 4 Years (Honours)"],
            medium: ["English"],
            text: "##### 2.2.4.5 Physical Science\n\n**(Course Code - 013)**\n\nCandidates must have obtained at least three 'S' passes at the G.C.E. (A/L) examination in Combined Mathematics, Physics, and Chemistry (or approved subject combination).\n\n- **Duration:** 3 Years (General) / 4 Years (Honours)\n- **Medium:** English",
          },
        ],
      },
      "019": {
        course_name: "Computer Science",
        blocks: [
          {
            title: "Computer Science",
            section: "2.2.4.12",
            pages: [84],
            citation: "Handbook §2.2.4.12, p. 84",
            degree_programmes: ["Bachelor of Science in Computer Science"],
            duration: ["3 Years / 4 Years (Honours)"],
            medium: ["English"],
            text: "##### 2.2.4.12 Computer Science\n\n**(Course Code - 019)**\n\nOffered at the University of Colombo School of Computing (UCSC). Requires Combined Mathematics, Physics, and Chemistry or ICT at A/L, plus minimum Credit pass in O/L Mathematics and English.",
          },
        ],
      },
      "022": {
        course_name: "Information Technology",
        blocks: [
          {
            title: "Information Technology",
            section: "2.2.4.15",
            pages: [87],
            citation: "Handbook §2.2.4.15, p. 87",
            degree_programmes: ["Bachelor of Science Honours in Information Technology"],
            duration: ["4 Years"],
            medium: ["English"],
            text: "##### 2.2.4.15 Information Technology\n\n**(Course Code - 022)**\n\nCandidates must pass the **Aptitude Test** conducted by the University of Moratuwa in addition to meeting A/L and O/L requirements.",
          },
        ],
      },
      "008": {
        course_name: "Engineering",
        blocks: [
          {
            title: "Engineering",
            section: "2.2.3.1",
            pages: [64],
            citation: "Handbook §2.2.3.1, p. 64",
            degree_programmes: ["Bachelor of the Science of Engineering Honours"],
            duration: ["4 Years"],
            medium: ["English"],
            text: "##### 2.2.3.1 Engineering\n\n**(Course Code - 008)**\n\nRequires at least Credit ('C') passes in Combined Mathematics, Physics, and Chemistry at one and the same sitting, plus O/L Credit pass in English.",
          },
        ],
      },
      "105": {
        course_name: "Data Science & Analytics",
        blocks: [
          {
            title: "Data Science & Analytics",
            section: "2.2.4.28",
            pages: [96],
            citation: "Handbook §2.2.4.28, p. 96",
            degree_programmes: ["Bachelor of Science Honours in Data Science & Analytics"],
            duration: ["4 Years"],
            medium: ["English"],
            text: "##### 2.2.4.28 Data Science & Analytics\n\n**(Course Code - 105)**\n\nNewly introduced honours degree programme focusing on statistical modelling, machine learning, and applied analytics.",
          },
        ],
      },
    },
    notes: [
      "Demo mode active: showing sample courses so you can verify the UI without a running backend.",
    ],
  };

  return {
    report,
    used_llm: Boolean(req.use_llm),
  };
}

const mockCareerJobs = new Map<string, { startedAt: number }>();

export function buildMockCareerStatus(course: string): CareerStatus {
  if (course === "Physical Science" || course === "Computer Science") {
    return {
      course,
      available: true,
      missing_keys: [],
      outlook: {
        generated_at: "2026-11-13T09:40:22.800046+00:00",
        status: "success",
        sources: 18,
        overall: {
          label: "positive",
          summary: `Graduates in ${course} from Sri Lankan state universities have strong demand across local tech, analytics, research, and postgraduate pathways.`,
          confidence: "medium",
          evidence_refs: ["E001", "E008"],
        },
      },
      job: null,
    };
  }

  const jobEntry = mockCareerJobs.get(course);
  if (jobEntry) {
    const elapsedMs = Date.now() - jobEntry.startedAt;
    if (elapsedMs < 6000) {
      return {
        course,
        available: true,
        missing_keys: [],
        outlook: null,
        job: {
          course,
          state: "running",
          message: `Demo research running for ${course} (synthesizing web sources)…`,
          started: jobEntry.startedAt / 1000,
        },
      };
    }

    return {
      course,
      available: true,
      missing_keys: [],
      outlook: {
        generated_at: new Date().toISOString(),
        status: "success",
        sources: 14,
        overall: {
          label: "positive",
          summary: `Demo career outlook for ${course}: solid industry and academic opportunities in Sri Lanka and internationally.`,
          confidence: "medium",
        },
      },
      job: {
        course,
        state: "done",
        message: "Completed demo career research.",
        started: jobEntry.startedAt / 1000,
        finished: Date.now() / 1000,
      },
    };
  }

  return {
    course,
    available: true,
    missing_keys: [],
    outlook: null,
    job: null,
  };
}

export function startMockCareerResearch(course: string): CareerResearchResponse {
  mockCareerJobs.set(course, { startedAt: Date.now() });
  return {
    ...buildMockCareerStatus(course),
    message: `Started demo career research for ${course}.`,
  };
}

export function buildMockChatResponse(req: ChatRequest): ChatResponse {
  const courseName = req.course.course_name || req.course.course_code;
  const q = req.question.toLowerCase();

  let answer = `Based on the UGC 2024/2025 Student Handbook for **${courseName}** (${req.course.course_code}), you are eligible to apply with your current A/L combination. [S1]`;

  if (q.includes("aptitude")) {
    const hasAptitude = Boolean(req.course.aptitude_test);
    answer = hasAptitude
      ? `Yes. **${courseName}** requires passing an aptitude test conducted by the university in addition to your A/L Z-score. [S1]`
      : `No aptitude test is listed for **${courseName}** (${req.course.uni_code ?? req.course.course_code}) in the handbook section. [S1]`;
  } else if (q.includes("o/l") || q.includes("ol")) {
    answer = `O/L requirements for **${courseName}** are checked against Science, English, and Mathematics grades. Check the O/L Requirements chips in the Overview tab for your exact status. [S1]`;
  } else if (q.includes("career")) {
    answer = `Graduates in **${courseName}** pursue roles in software, engineering, analytics, teaching, and postgraduate research in Sri Lanka and abroad. [S1] [C]`;
  }

  return {
    answer,
    status: "answered",
    sources: [
      {
        id: "S1",
        kind: "course_section",
        title: courseName,
        citation: `Handbook §2.2 (${req.course.course_code})`,
      },
      ...(q.includes("career")
        ? [
            {
              id: "C",
              kind: "career_outlook",
              title: `Career research: ${courseName} (Sri Lanka)`,
              citation: "Demo web research",
              links: [
                {
                  id: "E001",
                  title: "UGC Sri Lanka Admissions",
                  url: "https://www.ugc.ac.lk/",
                },
              ],
            },
          ]
        : []),
    ],
    career_research: q.includes("career"),
    notes: ["Demo mode response — connect make api for live handbook RAG & OpenAI answers."],
    model: "demo-mode",
    career: buildMockCareerStatus(courseName),
  };
}
