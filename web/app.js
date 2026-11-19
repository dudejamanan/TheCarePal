const byId = id => document.getElementById(id);
const select = byId("request");
const ranking = byId("ranking");
const find = byId("find");
const results = byId("matches");
const status = byId("status");
const api = byId("api");
let requests = [];

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("Request failed");
  return response.json();
}

function showRequirements() {
  const request = requests.find(item => item.id === select.value);
  const fields = [
    ["City", request.city], ["Care", request.skill], ["Language", request.language],
    ["Shift", request.shift], ["Previous nurse", request.previous_nurse_id ?? "None"]
  ];
  byId("requirements").replaceChildren(
    ...fields.flatMap(([label, value]) => [element("dt", label), element("dd", value)])
  );
}

function matchCard(match) {
  const card = element("li");
  const heading = element("div", undefined, "match-header");
  heading.append(
    element("span", match.rank, "rank"),
    element("strong", "Nurse " + match.nurse.id),
    element("span", match.score.toFixed(1) + " / 100", "score")
  );
  const meta = [match.distance_km.toFixed(1) + " km", match.nurse.rating.toFixed(1) + " / 5 rating",
    match.nurse.years + " years"];
  if (match.returning_nurse) meta.push("Returning nurse");

  const details = element("details");
  const breakdown = element("div", undefined, "breakdown");
  breakdown.append(element("p", match.explanation));
  breakdown.append(element("p", "Eligible for " + match.eligibility.join(" · ")));
  for (const factor of match.score_breakdown) {
    const row = element("div", undefined, "factor");
    const label = element("span", factor.factor);
    label.append(element("small", factor.reason));
    const points = factor.points.toFixed(2);
    const display = factor.factor === "Recent first placements"
      ? points + " pts" : points + " / " + factor.max_points + " pts";
    row.append(label, element("strong", display));
    breakdown.append(row);
  }
  details.append(element("summary", "Why this match?"), breakdown);
  card.append(heading, element("p", meta.join(" · "), "match-meta"), details);
  return card;
}

function drawMap(request, matches) {
  byId("map-panel").hidden = !matches.length;
  if (!matches.length) return;
  const canvas = byId("map");
  canvas.setAttribute("aria-label", "Schematic map of the patient and " + matches.length +
    " ranked nurses in " + request.city + ". Distances are listed in the results.");
  const ctx = canvas.getContext("2d");
  const width = 320;
  const height = 208;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.scale(ratio, ratio);
  const points = [request, ...matches.map(match => match.nurse)];
  const longitudeScale = Math.cos(request.lat * Math.PI / 180);
  const offsets = points.map(point => [
    (point.lon - request.lon) * longitudeScale, request.lat - point.lat
  ]);
  const xs = offsets.map(point => point[0]);
  const ys = offsets.map(point => point[1]);
  const left = Math.min(...xs), right = Math.max(...xs);
  const top = Math.min(...ys), bottom = Math.max(...ys);
  const scale = Math.min((width - 56) / Math.max(right - left, .01),
    (height - 56) / Math.max(bottom - top, .01));
  const pixels = offsets.map(([x, y]) => [
    width / 2 + (x - (left + right) / 2) * scale,
    height / 2 + (y - (top + bottom) / 2) * scale
  ]);

  ctx.fillStyle = "#e6f2f8";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#c3dae6";
  for (let x = 0; x < width; x += 24) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += 24) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.font = "bold 12px system-ui";
  ctx.fillStyle = "#12334a";
  ctx.fillText("↑ N", 10, 18);
  ctx.strokeStyle = "#6d9bb5";
  ctx.setLineDash([4, 4]);
  for (const [x, y] of pixels.slice(1)) {
    ctx.beginPath();
    ctx.moveTo(...pixels[0]);
    ctx.lineTo(x, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  pixels.forEach(([x, y], index) => {
    ctx.fillStyle = index === 0 ? "#12334a" : "#245e83";
    ctx.beginPath();
    ctx.arc(x, y, 11, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.fillText(index === 0 ? "P" : index, x, y);
  });
}

function clearMatches(message) {
  results.replaceChildren();
  api.hidden = true;
  byId("map-panel").hidden = true;
  status.textContent = message;
}

async function showMatches() {
  find.disabled = true;
  select.disabled = true;
  ranking.disabled = true;
  clearMatches("Finding eligible nurses…");
  const query = ranking.value === "learned" ? "?ranking=learned" : "";
  const path = "/api/matches/" + encodeURIComponent(select.value) + query;
  try {
    const {request, eligible_count, matches} = await getJson(path);
    status.textContent = matches.length
      ? "Showing " + matches.length + " of " + eligible_count + " eligible nurses."
      : "No eligible nurses for this request. Choose another sample to explore availability.";
    results.replaceChildren(...matches.map(matchCard));
    drawMap(request, matches);
    api.href = path;
    api.hidden = false;
  } catch {
    clearMatches("Could not load matches. Select Find matches to try again.");
  } finally {
    find.disabled = false;
    select.disabled = false;
    ranking.disabled = false;
  }
}

async function start() {
  try {
    const data = await getJson("/api/requests");
    requests = data.requests;
    for (const request of requests) {
      const option = element("option", request.id + " · " + request.city + " · " + request.skill);
      option.value = request.id;
      select.append(option);
    }
    byId("dataset").textContent = data.nurse_count + " synthetic nurses · " + requests.length + " sample requests";
    showRequirements();
    await showMatches();
  } catch {
    status.textContent = "Could not load sample requests. Reload the page to try again.";
  }
}

select.addEventListener("change", () => {
  showRequirements();
  clearMatches("Select Find matches to rank nurses for this request.");
});
find.addEventListener("click", showMatches);
ranking.addEventListener("change", showMatches);
start();
