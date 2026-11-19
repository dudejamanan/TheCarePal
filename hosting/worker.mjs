// Match Python's round(value, 2), including binary-float ties to even.
function round(value) {
  if (value === 0) return 0;
  const buffer = new ArrayBuffer(8);
  const view = new DataView(buffer);
  view.setFloat64(0, Math.abs(value));
  const bits = view.getBigUint64(0);
  const exponent = Number((bits >> 52n) & 2047n);
  const mantissa = (bits & ((1n << 52n) - 1n)) | (exponent ? 1n << 52n : 0n);
  const power = (exponent || 1) - 1023 - 52;
  const numerator = mantissa * 100n * (power > 0 ? 1n << BigInt(power) : 1n);
  const denominator = power < 0 ? 1n << BigInt(-power) : 1n;
  let whole = numerator / denominator;
  const remainder = numerator % denominator;
  if (2n * remainder > denominator ||
      (2n * remainder === denominator && whole % 2n === 1n)) whole += 1n;
  return Math.sign(value) * Number(whole) / 100;
}
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {"content-type": "application/json; charset=utf-8", "cache-control": "no-store",
  "x-content-type-options": "nosniff"}
});

function distanceKm(a, b) {
  const rad = degrees => degrees * Math.PI / 180;
  const lat1 = rad(a.lat), lat2 = rad(b.lat);
  const h = Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}

function recommend(request, mode) {
  const weights = dataset.weights[mode];
  const candidates = dataset.nurses.filter(n =>
    n.city === request.city && n.skills.includes(request.skill) &&
    n.languages.includes(request.language) && n.availability.includes(request.shift)
  ).map(nurse => {
    const distance = distanceKm(request, nurse);
    const returning = nurse.id === request.previous_nurse_id;
    const parts = [
      ["Distance", weights.distance * Math.max(0, 1 - distance / 25), weights.distance,
        distance.toFixed(1) + " km straight-line distance"],
      ["Rating", weights.rating * nurse.rating / 5, weights.rating, nurse.rating.toFixed(1) + " out of 5"],
      ["Experience", weights.experience * Math.min(nurse.years / 12, 1), weights.experience,
        nurse.years + " years, scoring capped at 12"],
      ["Continuity", weights.continuity * Number(returning), weights.continuity,
        returning ? "Previously cared for this patient" : "New to this patient"],
      ["Recent first placements", 0, 8, "Ranked first 0 times in the recent history"]
    ];
    return { nurse, distance_km: round(distance), score: round(parts.reduce((sum, p) => sum + p[1], 0)),
      returning_nurse: returning,
      eligibility: [request.skill, request.language, request.shift, request.city],
      score_breakdown: parts.map(([factor, points, max_points, reason]) =>
        ({factor, points: round(points), max_points, reason})) };
  });
  candidates.sort((a, b) => b.score - a.score || a.distance_km - b.distance_km ||
    a.nurse.id.localeCompare(b.nurse.id));
  const matches = candidates.slice(0, 5).map((match, i) => ({
    ...match, rank: i + 1,
    explanation: "Meets all requirements. Ranked #" + (i + 1) + " by adjusted score (" +
      match.score.toFixed(2) + "/100). Ties use distance, then nurse ID."
  }));
  return {request, eligible_count: candidates.length, matches, ranking: mode, weights};
}

function validate(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Send a JSON object.");
  }
  const options = {city: Object.keys(dataset.cities), skill: dataset.skills,
    language: dataset.languages, shift: dataset.shifts};
  for (const [field, values] of Object.entries(options)) {
    if (!values.includes(payload[field])) throw new Error(field + " must be one of: " + values.join(", ") + ".");
  }
  const center = dataset.cities[payload.city];
  for (const [i, field] of ["lat", "lon"].entries()) {
    const value = payload[field];
    if (typeof value !== "number" || !Number.isFinite(value) || Math.abs(value - center[i]) > .2) {
      throw new Error(field + " must be a numeric coordinate within 0.2 degrees of the city center.");
    }
  }
  const previous = payload.previous_nurse_id ?? null;
  if (previous !== null && !dataset.nurses.some(n => n.id === previous)) {
    throw new Error("previous_nurse_id must be a known nurse ID or null.");
  }
  return Object.fromEntries([...Object.keys(options), "lat", "lon"].map(key => [key, payload[key]])
    .concat([["previous_nurse_id", previous]]));
}

export default {
  async fetch(incoming) {
    const url = new URL(incoming.url);
    const path = url.pathname;
    if (incoming.method === "GET" && assets[path]) {
      return new Response(assets[path].body, {headers: {
        "content-type": assets[path].type + "; charset=utf-8", "x-content-type-options": "nosniff"
      }});
    }
    if (incoming.method === "GET" && path === "/api/requests") {
      return json({requests: dataset.requests, nurse_count: dataset.nurses.length});
    }
    let request;
    if (incoming.method === "GET" && path.startsWith("/api/matches/")) {
      request = dataset.requests.find(r => r.id === path.slice("/api/matches/".length));
      if (!request) return json({error: "Unknown care request ID."}, 404);
    } else if (incoming.method === "POST" && path === "/api/matches") {
      if (incoming.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        return json({error: "Send application/json."}, 415);
      }
      const reader = incoming.body?.getReader();
      if (!reader) return json({error: "Request body is required."}, 400);
      const chunks = [];
      let length = 0;
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > 4096) {
          await reader.cancel();
          return json({error: "Request body exceeds 4 KB."}, 413);
        }
        chunks.push(value);
      }
      const body = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
      try {
        request = validate(JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(body)));
      } catch (error) {
        return json({error: error.message}, 400);
      }
    } else {
      return json({error: "Route not found."}, 404);
    }
    const modes = url.searchParams.getAll("ranking");
    const mode = modes[0] ?? "default";
    if (modes.length > 1 || !Object.hasOwn(dataset.weights, mode)) {
      return json({error: "ranking must be default or learned."}, 400);
    }
    return json(recommend(request, mode));
  }
};
