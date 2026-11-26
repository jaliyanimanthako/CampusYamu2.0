/**
 * OpenAPI TypeScript definitions for CampusYamu API (/openapi.json).
 * Regenerate against a running server with: npm run gen:api
 */

export interface paths {
  "/v1/health": {
    get: operations["health_v1_health_get"];
  };
  "/v1/options": {
    get: operations["options_v1_options_get"];
  };
  "/v1/courses": {
    get: operations["courses_v1_courses_get"];
  };
  "/v1/recommendations": {
    post: operations["recommendations_v1_recommendations_post"];
  };
  "/v1/chat": {
    post: operations["chat_v1_chat_post"];
  };
  "/v1/career-outlook": {
    get: operations["career_outlook_v1_career_outlook_get"];
  };
  "/v1/career-outlook/research": {
    post: operations["career_research_v1_career_outlook_research_post"];
  };
}

export interface components {
  schemas: {
    SubjectGrade: {
      subject: string;
      grade?: string;
    };
    RecommendationRequest: {
      stream: string;
      al: components["schemas"]["SubjectGrade"][];
      ol?: components["schemas"]["SubjectGrade"][];
      cgt: number;
      z_score?: number | null;
      admission_district: string;
      home_district?: string | null;
      home_town?: string | null;
      /** @deprecated Old forms only: a home DS division, mapped to its main town */
      ds_division?: string | null;
      preferences?: string;
      use_llm?: boolean;
      suggestions?: number;
    };
    RecommendationResponse: {
      report: Record<string, unknown>;
      used_llm: boolean;
    };
    ChatTurn: {
      role: "user" | "assistant";
      content: string;
    };
    ChatCourse: {
      course_code: string;
      course_name?: string;
      [key: string]: unknown;
    };
    ChatRequest: {
      question: string;
      course: components["schemas"]["ChatCourse"];
      student?: Record<string, unknown>;
      history?: components["schemas"]["ChatTurn"][];
    };
    CareerOutlookSummary: {
      generated_at?: string | null;
      status?: string | null;
      sources?: number;
      overall?: unknown;
    };
    CareerJob: {
      course: string;
      state: "running" | "done" | "failed";
      message?: string;
      started?: number | null;
      finished?: number | null;
      [key: string]: unknown;
    };
    CareerStatus: {
      course: string;
      available: boolean;
      missing_keys: string[];
      outlook?: components["schemas"]["CareerOutlookSummary"] | null;
      job?: components["schemas"]["CareerJob"] | null;
    };
    CareerResearchRequest: {
      course: string;
    };
    CareerResearchResponse: components["schemas"]["CareerStatus"] & {
      message: string;
    };
    ChatSource: {
      id: string;
      kind: string;
      title?: string | null;
      citation?: string | null;
      links?: unknown[] | null;
      [key: string]: unknown;
    };
    ChatResponse: {
      answer: string;
      status: "answered" | "partly_answered" | "not_in_sources";
      sources: components["schemas"]["ChatSource"][];
      career_research: boolean;
      notes: string[];
      model: string;
      career?: components["schemas"]["CareerStatus"] | null;
    };
    StreamHint: {
      defaults: string[];
      source: string;
      allowed?: string[];
      required_any?: string[];
      required_all?: string[];
      [key: string]: unknown;
    };
    Options: {
      streams: string[];
      stream_hints: Record<string, components["schemas"]["StreamHint"]>;
      al_subjects: string[];
      al_grades: string[];
      ol_subjects: string[];
      ol_grades: string[];
      districts: string[];
      towns: Record<string, string[]>;
      llm_available: boolean;
    };
    Health: {
      ok: boolean;
      version: string;
      llm_available: boolean;
    };
    ErrorResponse: {
      errors: string[];
    };
  };
}

export interface operations {
  health_v1_health_get: {
    responses: {
      200: {
        content: {
          "application/json": components["schemas"]["Health"];
        };
      };
    };
  };
  options_v1_options_get: {
    responses: {
      200: {
        content: {
          "application/json": components["schemas"]["Options"];
        };
      };
    };
  };
  courses_v1_courses_get: {
    responses: {
      200: {
        content: {
          "application/json": string[];
        };
      };
    };
  };
  recommendations_v1_recommendations_post: {
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecommendationRequest"];
      };
    };
    responses: {
      200: {
        content: {
          "application/json": components["schemas"]["RecommendationResponse"];
        };
      };
    };
  };
  chat_v1_chat_post: {
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChatRequest"];
      };
    };
    responses: {
      200: {
        content: {
          "application/json": components["schemas"]["ChatResponse"];
        };
      };
    };
  };
  career_outlook_v1_career_outlook_get: {
    parameters: {
      query: {
        course: string;
      };
    };
    responses: {
      200: {
        content: {
          "application/json": components["schemas"]["CareerStatus"];
        };
      };
    };
  };
  career_research_v1_career_outlook_research_post: {
    requestBody: {
      content: {
        "application/json": components["schemas"]["CareerResearchRequest"];
      };
    };
    responses: {
      202: {
        content: {
          "application/json": components["schemas"]["CareerResearchResponse"];
        };
      };
    };
  };
}
