import { NextResponse } from "next/server";

const TOKEN_URL = "https://api.prokerala.com/token";
const API_BASE_URL = "https://api.prokerala.com/v2";

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

type CachedToken = TokenResponse & { expires_at: number };

let cachedToken: CachedToken | null = null;

async function fetchOAuthToken(): Promise<TokenResponse> {
  const clientId = process.env.PROKERALA_CLIENT_ID;
  const clientSecret = process.env.PROKERALA_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    throw new Error("Missing PROKERALA_CLIENT_ID or PROKERALA_CLIENT_SECRET environment variables");
  }

  if (cachedToken && cachedToken.expires_at > Date.now() + 30_000) {
    return cachedToken;
  }

  const params = new URLSearchParams({
    grant_type: "client_credentials",
    client_id: clientId,
    client_secret: clientSecret,
  });

  const response = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });

  if (!response.ok) {
    throw new Error(`Failed to acquire token: ${response.status} ${await response.text()}`);
  }

  const tokenPayload = (await response.json()) as TokenResponse;
  cachedToken = {
    ...tokenPayload,
    expires_at: Date.now() + tokenPayload.expires_in * 1000,
  };
  return tokenPayload;
}

function appendNestedParams(
  params: URLSearchParams,
  prefix: string,
  data: Record<string, string | number | boolean | null | undefined>,
) {
  Object.entries(data).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    params.append(`${prefix}[${key}]`, typeof value === "boolean" ? String(value).toLowerCase() : String(value));
  });
}

async function prokeralaRequest(path: string, searchParams: URLSearchParams) {
  const token = await fetchOAuthToken();
  const url = new URL(`${API_BASE_URL}${path}`);
  searchParams.forEach((value, key) => {
    url.searchParams.append(key, value);
  });

  const response = await fetch(url, {
    headers: {
      Authorization: `${token.token_type} ${token.access_token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Prokerala API error for ${path}: ${response.status} ${await response.text()}`);
  }

  return response.json();
}

type RequestBody = {
  name?: string;
  birthDate: string;
  birthTime: string;
  timezoneOffset: string;
  birthLatitude?: number;
  birthLongitude?: number;
  currentLatitude?: number;
  currentLongitude?: number;
  transitDateTime?: string;
  houseSystem?: string;
  orb?: string;
  ayanamsa?: number;
  language?: string;
  openaiModel?: string;
  deepseekModel?: string;
};

type PlanetPosition = Record<string, unknown>;

type TransitPayload = {
  data?: {
    transit_details?: {
      planet_positions?: PlanetPosition[];
    };
    transit_natal_aspects?: PlanetPosition[];
  };
};

type NatalPayload = {
  data?: {
    planet_positions?: PlanetPosition[];
    angles?: PlanetPosition[];
    aspects?: PlanetPosition[];
  };
};

function formatPlanet(row: PlanetPosition): string {
  const name = String(row.name ?? row?.planet?.name ?? "?");
  const zodiac = String(row?.zodiac?.name ?? "");
  const degree = typeof row.degree === "number" ? `${row.degree.toFixed(2)}°` : row.degree ?? "";
  const house = row.house_number ?? row.houseNumber ?? row.house;
  const retrograde = row.is_retrograde ? " (R)" : "";
  const houseStr = house !== undefined ? ` (House ${house})` : "";
  return `${name}: ${degree} ${zodiac}${houseStr}${retrograde}`.trim();
}

function formatAspect(row: PlanetPosition): string {
  const planetOne = row?.planet_one?.name ?? row?.planetOne?.name ?? row?.planet_one_name ?? "?";
  const planetTwo = row?.planet_two?.name ?? row?.planetTwo?.name ?? row?.planet_two_name ?? "?";
  const aspectName = row?.aspect?.name ?? row?.name ?? "aspect";
  const orb = typeof row.orb === "number" ? ` (orb ${row.orb.toFixed(2)})` : "";
  return `${planetOne} ${aspectName} ${planetTwo}${orb}`;
}

function buildInsightPrompt(natal: NatalPayload, transit: TransitPayload, personName?: string): string {
  const natalPlanets = natal.data?.planet_positions ?? [];
  const natalAngles = natal.data?.angles ?? [];
  const natalAspects = natal.data?.aspects ?? [];
  const transitPlanets = transit.data?.transit_details?.planet_positions ?? [];
  const transitAspects = transit.data?.transit_natal_aspects ?? [];

  const lines: string[] = [
    "You are an expert western astrologer. Provide a concise interpretation using the natal placements and current transits.",
  ];
  if (personName) {
    lines.push(`The person\'s name is ${personName}.`);
  }

  if (natalPlanets.length) {
    lines.push("\nNatal planet positions:");
    lines.push(...natalPlanets.map((planet) => `- ${formatPlanet(planet)}`));
  }
  if (natalAngles.length) {
    lines.push("\nKey angles:");
    lines.push(...natalAngles.map((planet) => `- ${formatPlanet(planet)}`));
  }
  if (natalAspects.length) {
    lines.push("\nNatal aspects:");
    lines.push(...natalAspects.map((aspect) => `- ${formatAspect(aspect)}`));
  }
  if (transitPlanets.length) {
    lines.push("\nCurrent transit positions:");
    lines.push(...transitPlanets.map((planet) => `- ${formatPlanet(planet)}`));
  }
  if (transitAspects.length) {
    lines.push("\nImportant transit-to-natal aspects:");
    lines.push(...transitAspects.map((aspect) => `- ${formatAspect(aspect)}`));
  }

  lines.push(
    "\nSummarize the natal themes in three bullet points and highlight three short-term transit influences. Keep the tone practical and supportive.",
  );

  return lines.join("\n");
}

async function callOpenAI(prompt: string, model?: string): Promise<string | null> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return null;
  }

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: model ?? "gpt-4o-mini",
      messages: [
        { role: "system", content: "You are a helpful astrology expert." },
        { role: "user", content: prompt },
      ],
      temperature: 0.7,
      max_tokens: 600,
    }),
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  const content: string | undefined = data?.choices?.[0]?.message?.content;
  return content ?? null;
}

async function callDeepSeek(prompt: string, model?: string): Promise<string | null> {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    return null;
  }

  const response = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: model ?? "deepseek-chat",
      messages: [
        { role: "system", content: "You are a helpful astrology expert." },
        { role: "user", content: prompt },
      ],
      temperature: 0.7,
      max_tokens: 600,
    }),
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  const content: string | undefined = data?.choices?.[0]?.message?.content;
  return content ?? null;
}

function toIsoString(date: string, time: string, offset: string): string {
  const normalizedOffset = offset.startsWith("+") || offset.startsWith("-") ? offset : `+${offset}`;
  return `${date}T${time}${normalizedOffset}`;
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as RequestBody;
    const {
      name,
      birthDate,
      birthTime,
      timezoneOffset,
      birthLatitude,
      birthLongitude,
      currentLatitude,
      currentLongitude,
      transitDateTime,
      houseSystem = "placidus",
      orb = "default",
      ayanamsa = 0,
      language = "en",
      openaiModel,
      deepseekModel,
    } = body;

    if (!birthDate || !birthTime || birthLatitude === undefined || birthLongitude === undefined) {
      return NextResponse.json(
        {
          error: "birthDate, birthTime, birthLatitude, and birthLongitude are required fields",
        },
        { status: 400 },
      );
    }

    const birthDateTime = toIsoString(birthDate, birthTime, timezoneOffset);
    const transitInstant = transitDateTime ?? new Date().toISOString();
    const currentCoords =
      currentLatitude !== undefined && currentLongitude !== undefined
        ? `${currentLatitude},${currentLongitude}`
        : `${birthLatitude},${birthLongitude}`;

    const natalParams = new URLSearchParams({
      house_system: houseSystem,
      orb,
      ayanamsa: String(ayanamsa),
    });
    appendNestedParams(natalParams, "profile", {
      datetime: birthDateTime,
      coordinates: `${birthLatitude},${birthLongitude}`,
      birth_time_unknown: false,
    });
    natalParams.append("la", language);
    natalParams.append("aspect_filter", "major");

    const transitParams = new URLSearchParams({
      house_system: houseSystem,
      orb,
      ayanamsa: String(ayanamsa),
      transit_datetime: transitInstant,
      current_coordinates: currentCoords,
    });
    appendNestedParams(transitParams, "profile", {
      datetime: birthDateTime,
      coordinates: `${birthLatitude},${birthLongitude}`,
      birth_time_unknown: false,
    });
    transitParams.append("la", language);

    const [natalChart, transitPositions] = await Promise.all([
      prokeralaRequest("/astrology/natal-chart", natalParams),
      prokeralaRequest("/astrology/transit-planet-position", transitParams),
    ]);

    const prompt = buildInsightPrompt(natalChart as NatalPayload, transitPositions as TransitPayload, name);

    let insight: string | null = await callOpenAI(prompt, openaiModel);
    if (!insight) {
      insight = await callDeepSeek(prompt, deepseekModel);
    }

    return NextResponse.json({
      natalChart,
      transitPositions,
      insight,
      prompt,
    });
  } catch (error) {
    console.error("Failed to process astrology request", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
