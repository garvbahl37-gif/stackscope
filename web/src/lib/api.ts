import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

// ------------------------------------------------------------------------------------------
// Types (mirrors the FastAPI marts; only the fields the UI reads)
// ------------------------------------------------------------------------------------------
export type Category = { id: string; label: string; technologies: number };
export type TechMeta = { tech: string; category: string; first_year: number; last_year: number; n_years: number; note: string | null };
export type Meta = {
  years: number[];
  categories: Category[];
  technologies: TechMeta[];
  countries: { iso3: string; country: string; region: string; respondents: number }[];
  regions: string[];
};

export type Finding = {
  rank: number; finding_id: string; theme: string; route: string; value: number; value_label: string;
  headline: string; detail: string;
};

export type Overview = {
  kpis: {
    respondents: number; waves: number; countries: number; technologies: number; tech_observations: number;
    pay_records: number; raw_mentions: number; raw_labels: number; checks_passed: number; checks_total: number;
  };
  findings: Finding[];
  by_year: { survey_year: number; respondents: number; professionals: number; effective_n: number; design_effect: number }[];
  ai: { survey_year: number; using_w: number; trust_w: number; distrust_w: number }[];
  remote: { survey_year: number; share_w: number }[];
  real_pay: { survey_year: number; fixed_mix_median_real: number }[];
  leaders: { category: string; category_label: string; tech: string; share_used_w: number; momentum: number }[];
  movers: { tech: string; category: string; odds_growth: number; share_first: number; share_last: number; first_year: number; trend: string }[];
};

export type SeriesPoint = { year: number; value: number | null; lo: number | null; hi: number | null; n: number };
export type TrendStats = { tech: string; odds_growth: number | null; odds_growth_lo: number | null; odds_growth_hi: number | null; q_value: number | null; trend: string; n_points: number };
export type Trends = { metric: string; series: { tech: string; category: string; points: SeriesPoint[] }[]; notes: { tech: string; note: string }[]; stats: TrendStats[] };

export type QuadrantPoint = {
  survey_year: number; tech: string; adoption: number; adoption_lo: number; adoption_hi: number; momentum: number;
  retention: number | null; attraction: number | null; net_desire: number | null; quadrant: string; base_n: number;
  adoption_threshold: number;
};
export type Quadrant = { category: string; years: number[]; points: QuadrantPoint[] };

export type Blip = {
  blip: number; sector: string; category: string; tech: string; survey_year: number; ring: string; share_used_w: number;
  momentum: number; retention_w: number | null; attraction_w: number | null; trend: string; odds_growth: number | null;
  adoption_pct_rank: number;
};

export type ForecastPoint = { tech: string; category: string; survey_year: number; share: number; lo80: number; hi80: number; kind: "actual" | "forecast"; model: string };
export type Backtest = { model: string; horizon: number; n: number; mae_pp: number; rmse_pp: number; skill_vs_naive: number; selected: boolean };
export type Forecast = {
  series: { tech: string; category: string; points: ForecastPoint[] }[];
  backtest: Backtest[]; indicator: { feature: string; coefficient: number }[]; forecastable: string[];
};

export type Mover = { tech: string; category: string; prev_share_used_w: number; share_used_w: number; delta_pp: number; q_value: number; significant: boolean };
export type Trajectory = {
  tech: string; category: string; first_year: number; last_year: number; n_points: number; share_first: number; share_last: number;
  change_pp: number; odds_growth: number | null; odds_growth_lo: number | null; odds_growth_hi: number | null; q_value: number | null; trend: string;
};

export type Concentration = {
  category: string;
  hhi: { survey_year: number; hhi: number; hhi_like_for_like: number; effective_competitors: number; cr3: number; cr5: number; leader: string; leader_share: number; structure: string; technologies: number }[];
  shares: { survey_year: number; tech: string; mindshare: number }[];
};

export type Retention = {
  year: number; category: string;
  leaderboard: { tech: string; retention: number; attraction: number; adoption: number; users_asked_want: number; churn: number }[];
  flows: { from_tech: string; to_tech: string; n: number; share_of_churners: number; from_churn_rate: number; destination_rank: number }[];
  net: { from_tech: string; to_tech: string; flow_forward: number; flow_backward: number; net_flow: number; net_ratio: number }[];
};

export type TechProfile = {
  info: TechMeta & { category_label: string };
  series: { survey_year: number; share_used_w: number; share_used_w_lo: number; share_used_w_hi: number; share_wanted_w: number | null; retention_w: number | null; attraction_w: number | null; rank_in_category: number; base_n: number }[];
  trend: Trajectory | null;
  quadrant: { survey_year: number; quadrant: string; momentum: number }[];
  premium: { scope: string; premium: number; premium_lo: number; premium_hi: number; q_value: number; significant: boolean }[];
  leaving_to: { to_tech: string; n: number; share_of_churners: number }[];
  arriving_from: { from_tech: string; n: number }[];
  paired_with: { tech: string; confidence: number; lift: number }[];
};

export type Benchmark = {
  segment: string; sub_segment: string | null; label?: string; n: number; p25_usd: number; median_usd: number; p75_usd: number;
  median_real: number; median_ppp: number | null; p25_ppp: number | null; p75_ppp: number | null;
};
export type Benchmarks = { cut: string; year: number; rows: Benchmark[]; overall: { n: number; median_usd: number; median_ppp: number } | null };

export type CountryYear = {
  iso3: string; country: string; iso_numeric: number; region: string; income_group: string | null; respondents: number; pay_n: number;
  median_pay_usd: number | null; median_pay_ppp: number | null; remote_share: number | null; ai_use_share: number | null;
  top_language: string | null; respondents_per_million: number | null; lon: number | null; lat: number | null;
};

export type Premium = {
  scope: string; tech: string; category: string; n_users: number; prevalence: number; coef: number; se: number; p_value: number;
  premium: number; premium_lo: number; premium_hi: number; raw_premium: number; q_value: number; significant: boolean;
};
export type PremiumResponse = { scope: string; rows: Premium[]; model: { n: number; r2: number; adj_r2: number; features: number; technologies: number; years: string; median_pay_real: number } | null; scopes: string[] };

export type WorkforceTrends = {
  real_pay: { survey_year: number; countries: number; fixed_mix_median_real: number; fixed_mix_median_ppp: number; raw_median_real: number }[];
  remote: { survey_year: number; category: string; share_w: number }[];
  remote_by_region: { survey_year: number; region: string; n: number; remote_w: number; hybrid_w: number; in_person_w: number }[];
  pay_by_year: { survey_year: number; n: number; median_usd: number; median_real: number; median_ppp: number }[];
};

export type EstimatorOptions = {
  countries: { iso3: string; country: string; region: string }[];
  roles: string[]; org_sizes: string[]; education: string[]; remote: string[]; industries: string[]; age_bands: string[]; ai_use: string[];
  technologies: { tech: string; category: string }[];
  metrics: Record<string, number>;
  importance: { group: string; mean_abs_shap: number; share: number }[];
  top_features: { label: string; grp: string; mean_abs_shap: number }[];
  price_base_year: number;
};
export type Profile = {
  country: string; dev_role: string; years_code: number; work_exp?: number | null; org_size: string; ed_level: string;
  remote_work: string; industry: string; age_band: string; ai_use: string; technologies: string[];
};
export type Estimate = {
  p10: number; p50: number; p90: number; baseline: number; country_median: number | null; coverage: number; price_base_year: number;
  contributions: { group: string; log_effect: number; multiplier: number }[];
  tech_effects: { tech: string; multiplier: number }[];
};

export type Segments = {
  profiles: {
    segment_id: number; name: string; respondents: number; share_w: number; median_pay_real: number | null; pay_n: number;
    ai_daily: number; remote_share: number; median_years_code: number; top_role: string; top_role_share: number; signature: string; most_used: string;
  }[];
  technologies: { segment_id: number; tech: string; category: string; prevalence: number; lift: number }[];
  regions: { segment_id: number; region: string; share_w: number }[];
  model: { k: number; silhouette: number; inertia: number; chosen: boolean }[];
};

export type NetworkNode = { survey_year: number; tech: string; category: string; prevalence: number; community: number; community_label: string; degree: number; betweenness: number; x: number; y: number };
export type Network = { year: number; years: number[]; nodes: NetworkNode[]; edges: { a: string; b: string; co_users: number; support: number; lift: number; npmi: number }[] };
export type Rules = { tech: string; rules: { consequent: string; co_users: number; support: number; confidence: number; lift: number }[] };

export type AiPulse = {
  years: { survey_year: number; n: number; using_w: number; planning_w: number; not_planning_w: number; sentiment_net: number; favorable_w: number; trust_net: number; trust_w: number; distrust_w: number; complex_net: number | null; threat_w: number | null }[];
  likert: { survey_year: number; question: string; answer: string; n: number; share_w: number }[];
  tasks: { survey_year: number; task: string; n: number; share_w: number; base_n: number }[];
  segments: { survey_year: number; dimension: string; segment: string; n: number; using_w: number; daily_w: number | null; trust_w: number; trust_net: number; sentiment_net: number; threat_w: number | null; agents_w: number | null }[];
  drivers: { model: string; variable: string; level: string; odds_ratio: number; or_lo: number; or_hi: number; p_value: number; q_value: number; n_level: number; reference: string; n_model: number; baseline_rate: number }[];
  tools: { tech: string; survey_year: number; share_used_w: number; retention_w: number | null }[];
};

export type Check = { check_id: string; dimension: string; description: string; metric: number; threshold: string; status: "pass" | "warn" | "fail"; blocker: boolean; detail: string };
/** One published Stack Overflow figure and its unweighted recomputation (dq.published_reconciliation). */
export type ReconRow = {
  survey_year: number; metric: string; item: string; group: string | null; published: number; ours: number; diff: number;
  unit: string; same_base: boolean; status: string; note: string | null; url: string;
};

export type Quality = {
  checks: Check[];
  completeness: { survey_year: number; field: string; completeness: number; asked: boolean }[];
  weights: { survey_year: number; respondents: number; design_effect: number; effective_n: number; min_weight: number; max_weight: number; iterations: number; max_margin_error: number; converged: boolean }[];
  targets: { dimension: string; category: string; target_share: number }[];
  schema_notes: { survey_year: number; note: string }[];
  layers: { layer: string; object: string; rows: number }[];
  coverage: { survey_year: number; status: string; labels: number; mentions: number }[];
  aliases: { tech: string; raw_labels: number; labels: string[]; mentions: number }[];
  tables: { schema_name: string; table_name: string; rows: number; column_count: number }[];
  reconciliation: ReconRow[];
};

export type SqlResult = { columns: { name: string; type: string }[]; rows: unknown[][]; row_count: number; truncated: boolean; elapsed_ms: number };
export type SqlSchema = { tables: { name: string; schema: string; rows: number; columns: { name: string; type: string }[] }[] };
export type SqlExample = { title: string; skill: string; sql: string };

// ------------------------------------------------------------------------------------------
// Fetching
// ------------------------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const q = (params: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && s.set(k, String(v)));
  const str = s.toString();
  return str ? `?${str}` : "";
};

const STATIC = { staleTime: Infinity, gcTime: 30 * 60 * 1000 } as const;
const KEEP = { ...STATIC, placeholderData: keepPreviousData } as const;

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta"), ...STATIC });
export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/overview"), ...STATIC });
export const useTrends = (techs: string[], metric: string) =>
  useQuery({ queryKey: ["trends", techs, metric], queryFn: () => api<Trends>(`/tech/trends${q({ techs: techs.join(","), metric })}`), enabled: techs.length > 0, ...KEEP });
export const useQuadrant = (category: string) =>
  useQuery({ queryKey: ["quadrant", category], queryFn: () => api<Quadrant>(`/tech/quadrant${q({ category })}`), ...KEEP });
export const useRadar = () => useQuery({ queryKey: ["radar"], queryFn: () => api<{ blips: Blip[]; sectors: string[]; rings: string[] }>("/tech/radar"), ...STATIC });
export const useForecast = (techs: string[]) =>
  useQuery({ queryKey: ["forecast", techs], queryFn: () => api<Forecast>(`/tech/forecast${q({ techs: techs.join(",") })}`), enabled: techs.length > 0, ...KEEP });
export const useMovers = (category?: string) =>
  useQuery({ queryKey: ["movers", category], queryFn: () => api<{ year: number; rows: Mover[] }>(`/tech/movers${q({ category })}`), ...KEEP });
export const useSelection = (category: string) =>
  useQuery({ queryKey: ["selection", category], queryFn: () => api<{ category: string; rows: { survey_year: number; mean_picks: number; respondents: number }[] }>(`/tech/selection${q({ category })}`), ...KEEP });
export const useTrajectories = (category?: string) =>
  useQuery({ queryKey: ["trajectories", category], queryFn: () => api<{ rows: Trajectory[] }>(`/tech/trajectories${q({ category })}`), ...KEEP });
export const useConcentration = (category: string) =>
  useQuery({ queryKey: ["concentration", category], queryFn: () => api<Concentration>(`/tech/concentration${q({ category })}`), ...KEEP });
export const useRetention = (category: string, year?: number) =>
  useQuery({ queryKey: ["retention", category, year], queryFn: () => api<Retention>(`/tech/retention${q({ category, year })}`), ...KEEP });
export const useTechProfile = (tech: string | null) =>
  useQuery({ queryKey: ["profile", tech], queryFn: () => api<TechProfile>(`/tech/profile/${encodeURIComponent(tech ?? "")}`), enabled: !!tech, ...KEEP });
export const useBenchmarks = (cut: string, year: number, region?: string) =>
  useQuery({ queryKey: ["benchmarks", cut, year, region], queryFn: () => api<Benchmarks>(`/talent/benchmarks${q({ cut, year, region })}`), ...KEEP });
export const usePayMap = (year: number) =>
  useQuery({ queryKey: ["paymap", year], queryFn: () => api<{ year: number; rows: CountryYear[] }>(`/talent/map${q({ year })}`), ...KEEP });
export const usePremium = (scope: string) =>
  useQuery({ queryKey: ["premium", scope], queryFn: () => api<PremiumResponse>(`/talent/premium${q({ scope })}`), ...KEEP });
export const useWorkforce = () => useQuery({ queryKey: ["workforce"], queryFn: () => api<WorkforceTrends>("/talent/trends"), ...STATIC });
export const useEstimatorOptions = () =>
  useQuery({ queryKey: ["estimator-options"], queryFn: () => api<EstimatorOptions>("/talent/estimator/options"), ...STATIC });
export const useEstimate = () =>
  useMutation({ mutationFn: (profile: Profile) => api<Estimate>("/talent/estimate", { method: "POST", body: JSON.stringify(profile) }) });
export const useSegments = () => useQuery({ queryKey: ["segments"], queryFn: () => api<Segments>("/segments"), ...STATIC });
export const useSegmentPoints = () =>
  useQuery({ queryKey: ["segment-points"], queryFn: () => api<{ points: { x: number; y: number; segment_id: number }[] }>("/segments/points"), ...STATIC });
export const useNetwork = (year: number) =>
  useQuery({ queryKey: ["network", year], queryFn: () => api<Network>(`/network${q({ year })}`), ...KEEP });
export const useRules = (tech: string | null, year: number) =>
  useQuery({ queryKey: ["rules", tech, year], queryFn: () => api<Rules>(`/network/rules${q({ tech, year })}`), enabled: !!tech, ...KEEP });
export const useAi = () => useQuery({ queryKey: ["ai"], queryFn: () => api<AiPulse>("/ai"), ...STATIC });
export const useQuality = () => useQuery({ queryKey: ["quality"], queryFn: () => api<Quality>("/quality"), ...STATIC });
export const useSqlSchema = () => useQuery({ queryKey: ["sql-schema"], queryFn: () => api<SqlSchema>("/sql/schema"), ...STATIC });
export const useSqlExamples = () => useQuery({ queryKey: ["sql-examples"], queryFn: () => api<{ examples: SqlExample[] }>("/sql/examples"), ...STATIC });
export const useRunSql = () =>
  useMutation({ mutationFn: (query: string) => api<SqlResult>("/sql/run", { method: "POST", body: JSON.stringify({ query }) }) });
