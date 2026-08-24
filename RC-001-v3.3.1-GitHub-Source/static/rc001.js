"use strict";

function getElement(id) {
    return document.getElementById(id);
}


function svgIcon(name, className = "icon") {
    return `<svg class="${className}" aria-hidden="true"><use href="/static/icons.svg#${name}"></use></svg>`;
}

function serviceMarkup(iconName, label, level = "warning") {
    const safeLevel = ["good", "warning", "critical", "neutral"].includes(level)
        ? level
        : "neutral";
    return `${svgIcon(iconName, "icon icon-sm")}<span class="service-indicator service-${safeLevel}"></span><span>${label}</span>`;
}

function getPollSeconds() {
    const parsedValue = Number(document.body?.dataset?.pollSeconds);
    return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : 10;
}

function formatDuration(seconds) {
    const total = Math.max(0, Number(seconds || 0));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m`;
    return "Just now";
}

function wanClass(wan) {
    if (wan.connected) return "connected";
    if (wan.standby) return "standby";
    return "down";
}

function wanIcon(wan) {
    return `<span class="wan-status-icon ${wanClass(wan)}">${svgIcon("router", "icon icon-sm")}</span>`;
}

function wanStatusText(wan) {
    if (wan.connected) return "Connected";
    if (wan.standby) return "Standby";
    return wan.message || "Down";
}

function wanServiceText(wan) {
    if (String(wan.id) !== "3") return wan.speed || "";
    if (wan.connected) return "5G Active Offload";
    if (wan.standby) return "5G Standby";
    return "5G Unavailable";
}

function latencyClass(ping) {
    if (ping == null) return "";
    if (ping < 30) return "latency-good";
    if (ping < 60) return "latency-warning";
    return "latency-poor";
}

function getInternetQuality(ping) {
    if (ping == null) return { text: "Waiting", className: "quality-unknown" };
    if (ping < 30) return { text: "Excellent", className: "quality-excellent" };
    if (ping < 60) return { text: "Good", className: "quality-good" };
    if (ping < 100) return { text: "Fair", className: "quality-fair" };
    return { text: "Poor", className: "quality-poor" };
}

function getJitterQuality(jitter) {
    if (jitter == null) return { text: "Waiting", className: "quality-unknown" };
    if (jitter < 10) return { text: "Very Stable", className: "jitter-excellent" };
    if (jitter < 20) return { text: "Stable", className: "jitter-good" };
    if (jitter < 40) return { text: "Variable", className: "jitter-variable" };
    return { text: "Unstable", className: "jitter-poor" };
}

function formatSpeedtestAge(timestamp) {
    if (!timestamp) return "Waiting";
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(timestamp)));
    if (seconds < 60) return "Just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

function formatTestTime(timestamp) {
    if (!timestamp) return "--";
    return new Date(Number(timestamp) * 1000).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
    });
}

function setSpeedtestResultLink(resultUrl) {
    const link = getElement("speedtestResultLink");
    if (!link) return;

    if (typeof resultUrl === "string" && resultUrl.startsWith("https://")) {
        link.href = resultUrl;
        link.classList.remove("is-hidden");
    } else {
        link.removeAttribute("href");
        link.classList.add("is-hidden");
    }
}

function setPerformanceMeasurement(elementId, value, unit) {
    const element = getElement(elementId);
    if (!element) return;

    element.replaceChildren();

    if (value == null || value === "") {
        element.textContent = "--";
        return;
    }

    const number = document.createElement("span");
    number.className = "performance-number";
    number.textContent = String(value);

    const unitLabel = document.createElement("span");
    unitLabel.className = "performance-unit";
    unitLabel.textContent = unit;

    element.append(number, unitLabel);
}

function updateSpeedtest(speedtest) {
    const ids = [
        "speedDownload", "speedUpload", "speedPing", "speedJitter",
        "speedAge", "speedTestTime", "internetQuality", "jitterQuality",
        "speedServer", "speedServerLocation",
    ];
    if (ids.some((id) => !getElement(id))) {
        console.error("One or more Internet Performance elements are missing.");
        return;
    }

    if (!speedtest || !speedtest.timestamp) {
        getElement("speedDownload").textContent = "--";
        getElement("speedUpload").textContent = "--";
        getElement("speedPing").textContent = "--";
        getElement("speedJitter").textContent = "--";
        getElement("speedAge").textContent = "Waiting";
        getElement("speedTestTime").textContent = "--";
        getElement("internetQuality").textContent = "Waiting";
        getElement("internetQuality").className = "quality-label quality-unknown";
        getElement("jitterQuality").textContent = "Waiting";
        getElement("jitterQuality").className = "quality-label quality-unknown";
        getElement("speedServer").textContent = "Waiting";
        getElement("speedServer").title = "";
        getElement("speedServerLocation").textContent = "--";
        setSpeedtestResultLink(null);
        return;
    }

    setPerformanceMeasurement("speedDownload", speedtest.download, "Mbps");
    setPerformanceMeasurement("speedUpload", speedtest.upload, "Mbps");
    setPerformanceMeasurement("speedPing", speedtest.ping, "ms");
    getElement("speedPing").className = `performance-value ${latencyClass(speedtest.ping)}`.trim();
    setPerformanceMeasurement("speedJitter", speedtest.jitter, "ms");

    const latencyQuality = getInternetQuality(speedtest.ping);
    getElement("internetQuality").textContent = latencyQuality.text;
    getElement("internetQuality").className = `quality-label ${latencyQuality.className}`;

    const jitterQuality = getJitterQuality(speedtest.jitter);
    getElement("jitterQuality").textContent = jitterQuality.text;
    getElement("jitterQuality").className = `quality-label ${jitterQuality.className}`;

    const serverName = speedtest.server || "Unknown Server";
    getElement("speedServer").textContent = serverName;
    getElement("speedServer").title = serverName;
    getElement("speedServerLocation").textContent = speedtest.server_location || "--";
    getElement("speedAge").textContent = formatSpeedtestAge(speedtest.timestamp);
    getElement("speedTestTime").textContent = formatTestTime(speedtest.timestamp);

    const ageSeconds = Math.floor(Date.now() / 1000) - Number(speedtest.timestamp);
    getElement("speedAge").className = ageSeconds > 3900
        ? "performance-value performance-value-text speedtest-stale"
        : "performance-value performance-value-text";

    setSpeedtestResultLink(speedtest.result_url);
}

function determineExecutiveStatus(data) {
    const lightingStatus = String(data?.lighting_status || "").toLowerCase();
    const airQuality = data?.air_quality || {};
    const wans = Array.isArray(data?.wans) ? data.wans : [];

    if (lightingStatus === "offline") return { key: "offline", text: "INTERNET OFFLINE" };
    if (lightingStatus === "tmobile") return { key: "tmobile", text: "CELLULAR FAILOVER ACTIVE" };
    if (lightingStatus === "failover") return { key: "failover", text: "NETWORK REDUNDANCY REDUCED" };

    const primaryConnected = wans.filter(
        (wan) => ["1", "2"].includes(String(wan.id)) && wan.connected
    ).length;
    if (primaryConnected === 1) {
        return { key: "failover", text: "NETWORK REDUNDANCY REDUCED" };
    }
    if (airQuality.available && airQuality.data_status !== "stale" && Number(airQuality.aqi) >= 101) {
        return { key: "environment", text: "ENVIRONMENTAL ADVISORY" };
    }
    return { key: "normal", text: "ALL SYSTEMS OPERATIONAL" };
}

function updateSystemBanner(data) {
    const header = getElement("systemHeader");
    const statusText = getElement("statusText");
    const indicator = getElement("statusIndicator");
    const systemStatus = getElement("systemStatus");
    if (!header || !statusText || !indicator || !systemStatus) return;

    const executive = determineExecutiveStatus(data);
    const classes = {
        normal: ["normal", "banner-normal"],
        failover: ["failover", "banner-failover"],
        tmobile: ["tmobile", "banner-tmobile"],
        offline: ["offline", "banner-offline"],
        environment: ["environment", "banner-environment"],
    };
    const [statusClass, bannerClass] = classes[executive.key] || ["unknown", ""];
    statusText.textContent = executive.text;
    systemStatus.className = `status ${statusClass}`.trim();
    header.className = `header ${bannerClass}`.trim();
    indicator.className = `status-indicator status-indicator-${statusClass}`;
}

function applyHealthItem(key, item) {
    const dot = getElement(`health${key}Dot`);
    const value = getElement(`health${key}Value`);
    if (!dot || !value || !item) return;
    dot.className = `health-dot health-${item.level || "neutral"}`;
    value.textContent = item.state || "Unknown";
}

function updateHealth(health, airQuality) {
    applyHealthItem("Internet", health?.internet);
    applyHealthItem("Environment", health?.environment);
    applyHealthItem("Lighting", health?.lighting);
    applyHealthItem("Automation", health?.automation);

    const securityDot = getElement("healthSecurityDot");
    const securityValue = getElement("healthSecurityValue");
    if (securityDot && securityValue) {
        securityDot.className = "health-dot health-good";
        securityValue.textContent = "Ready";
    }

    const environmentDot = getElement("healthEnvironmentDot");
    const environmentValue = getElement("healthEnvironmentValue");
    if (environmentDot && environmentValue && airQuality?.available && airQuality.data_status !== "stale" && Number(airQuality.aqi) >= 101) {
        environmentDot.className = Number(airQuality.aqi) >= 151
            ? "health-dot health-critical"
            : "health-dot health-warning";
        environmentValue.textContent = Number(airQuality.aqi) >= 151
            ? "Air Quality Alert"
            : "Smoke Present";
    }
}

function updateFooter(data) {
    const peplinkLevel =
        data.system_information?.peplink?.level || "good";
    const wledLevel =
        data.system_information?.wled?.level || "warning";
    const environmentAvailable =
        data.temperature != null || data.humidity != null;

    const peplink = getElement("peplinkStatus");
    const wled = getElement("wledStatus");
    const controller = getElement("controllerStatus");

    if (peplink) {
        peplink.innerHTML = serviceMarkup(
            "router",
            "Peplink",
            peplinkLevel
        );
    }
    if (wled) {
        wled.innerHTML = serviceMarkup(
            "lightbulb",
            "WLED",
            wledLevel
        );
    }
    if (controller) {
        controller.innerHTML = serviceMarkup(
            "thermometer",
            "AC Infinity Environment",
            environmentAvailable ? "good" : "warning"
        );
    }
}

function setTextIfPresent(id, value) {
    const element = getElement(id);
    if (element) element.textContent = value;
}

function updateEnvironment(data) {
    setTextIfPresent(
        "temperature",
        data.temperature == null ? "N/A" : `${data.temperature}°F`
    );
    setTextIfPresent(
        "humidity",
        data.humidity == null ? "N/A" : `${data.humidity}%`
    );
    setTextIfPresent(
        "cabinetRuntime",
        formatDuration(data.uptime_seconds)
    );
    setTextIfPresent(
        "lightingPreset",
        data.lighting_label || "--"
    );
}


function formatAirQualityTime(value) {
    if (!value) return "--";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "--";
    return parsed.toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
    });
}

function renderAqiSparkline(history) {
    const svg = getElement("airQualitySparkline");
    if (!svg) return;

    const points = Array.isArray(history)
        ? history.filter((item) => Number.isFinite(Number(item.aqi)))
        : [];

    if (points.length < 2) {
        svg.innerHTML =
            '<text x="50" y="18" text-anchor="middle" ' +
            'class="aqi-sparkline-empty">Collecting initial AQI samples…</text>';
        return;
    }

    const values = points.map((item) => Number(item.aqi));
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const range = Math.max(1, maximum - minimum);

    const coordinates = values.map((value, index) => {
        const x = (index / (values.length - 1)) * 100;
        const y = 30 - ((value - minimum) / range) * 24;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

    svg.innerHTML =
        `<polyline points="${coordinates}" ` +
        'class="aqi-sparkline-line"></polyline>';
}


function updateOutdoorWeather(weather) {
    const temperatureElement = getElement("outdoorTemperature");
    const feelsLikeElement = getElement("outdoorFeelsLike");
    if (!temperatureElement || !feelsLikeElement) return;

    if (!weather?.available || weather.temperature == null) {
        temperatureElement.textContent = "--";
        feelsLikeElement.textContent = weather?.error
            ? "Weather unavailable"
            : "Feels like --";
        return;
    }

    temperatureElement.textContent =
        Number(weather.temperature).toFixed(1);

    feelsLikeElement.textContent =
        weather.apparent_temperature == null
            ? "Feels like --"
            : `Feels like ${Number(
                weather.apparent_temperature
            ).toFixed(1)}°F`;
}

function updateAirQuality(airQuality) {
    const card = getElement("airQualityCard");
    if (!card) return;

    const available = Boolean(
        airQuality?.available && airQuality.aqi != null
    );

    card.dataset.aqiLevel = available
        ? airQuality.level || "unknown"
        : "unknown";

    getElement("airQualityValue").textContent =
        available ? String(airQuality.aqi) : "--";
    getElement("airQualityCategory").textContent =
        available ? `${airQuality.category || "Current"} Air Quality` : "Unavailable";
    getElement("airQualityPollutant").textContent =
        available ? airQuality.pollutant || "AQI" : "EPA AirNow";
    getElement("airQualityLocation").textContent =
        available ? airQuality.reporting_area || "" : "";
    getElement("airQualityAdvisory").textContent = available
        ? airQuality.health_message || ""
        : airQuality?.error || "Waiting for current AirNow data.";
    const ageSeconds = Number(airQuality?.age_seconds || 0);
    const ageLabel = ageSeconds >= 60
        ? `${Math.floor(ageSeconds / 60)}m old`
        : `${Math.max(0, Math.floor(ageSeconds))}s old`;
    getElement("airQualityUpdated").textContent = available
        ? airQuality.data_status === "delayed"
            ? `Delayed • ${ageLabel}`
            : airQuality.data_status === "stale"
                ? `Stale • ${ageLabel}`
                : formatAirQualityTime(airQuality.updated_at)
        : "--";

    const trend = available ? airQuality.trend || "Stable" : "Waiting";
    getElement("airQualityTrend").textContent =
        trend === "Improving"
            ? "↘ Improving"
            : trend === "Worsening"
              ? "↗ Worsening"
              : trend === "Stable"
                ? "→ Stable"
                : trend;

    renderAqiSparkline(airQuality?.history || []);
}

function updateLightingControls(data) {
    const manualOverride = Boolean(data.manual_override);
    const activeStatus = String(data.lighting_status || "").toLowerCase();
    const statusContainer = getElement("lightingControlStatus");
    const statusText = getElement("lightingControlStatusText");
    const autoButton = getElement("returnToAutoButton");
    const autoBadge = getElement("automaticStateBadge");

    if (statusContainer && statusText) {
        statusContainer.className = manualOverride
            ? "control-status control-status-manual"
            : "control-status control-status-auto";
        statusText.textContent = manualOverride ? "Manual Override" : "Automatic";
    }

    if (autoButton) {
        autoButton.classList.toggle("is-active", !manualOverride);
        autoButton.setAttribute("aria-pressed", String(!manualOverride));
    }

    if (autoBadge) {
        autoBadge.innerHTML = manualOverride
            ? `${svgIcon("automation", "icon icon-sm")} Resume Auto`
            : `${svgIcon("check", "icon icon-sm")} Enabled`;
    }

    document.querySelectorAll("[data-light-status]").forEach((button) => {
        const isActive = manualOverride && button.dataset.lightStatus === activeStatus;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
    });
}

function formatMbps(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "--";
    if (number < 0.01) return "0.00";
    return number < 10 ? number.toFixed(2) : number.toFixed(1);
}

function updateSnmpStatus(snmp) {
    const element = getElement("snmpTelemetryStatus");
    if (!element) return;

    if (snmp?.available) {
        element.textContent = "Live telemetry";
        element.className = "telemetry-badge telemetry-live";
    } else {
        element.textContent = "Telemetry unavailable";
        element.className = "telemetry-badge telemetry-offline";
    }
}

function updateInternetRows(wans) {
    const container = getElement("internetRows");
    if (!container) return;

    container.innerHTML = (wans || []).map((wan) => {
        const telemetryAvailable = Boolean(wan.telemetry_available);
        const share = telemetryAvailable
            ? Math.max(0, Math.min(100, Number(wan.traffic_share_percent || 0)))
            : 0;

        const telemetry = telemetryAvailable
            ? `
                <div class="wan-telemetry">
                    <div class="wan-rate">
                        <span class="wan-rate-label">↓ Download</span>
                        <strong>${formatMbps(wan.download_mbps)} Mbps</strong>
                    </div>
                    <div class="wan-rate">
                        <span class="wan-rate-label">↑ Upload</span>
                        <strong>${formatMbps(wan.upload_mbps)} Mbps</strong>
                    </div>
                    <div class="wan-share">
                        <div class="wan-share-heading">
                            <span>Current traffic share</span>
                            <strong>${share.toFixed(1)}%</strong>
                        </div>
                        <div class="wan-share-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${share.toFixed(1)}">
                            <div class="wan-share-fill ${wanClass(wan)}" style="width: ${share}%"></div>
                        </div>
                    </div>
                </div>`
            : `<div class="wan-telemetry wan-telemetry-unavailable">Waiting for SNMP telemetry…</div>`;

        return `
            <div class="wan-row">
                <div class="row wan-summary-row">
                    <div class="label">${wanIcon(wan)} ${wan.name}</div>
                    <div class="value ${wanClass(wan)}">
                        ${wanStatusText(wan)}
                        <span class="wan-duration">• ${formatDuration(wan.state_duration_seconds)}</span>
                    </div>
                    <div class="value subtle">${wanServiceText(wan)}</div>
                    <div class="wan-route subtle">
                        ${wan.ip || "No IP"}&nbsp;&nbsp;→&nbsp;&nbsp;${wan.gateway || "No gateway"}
                    </div>
                </div>
                ${telemetry}
            </div>`;
    }).join("");
}

function eventClass(eventType) {
    const mapping = {
        speedtest: "event-speedtest",
        wan: "event-wan",
        lighting: "event-lighting",
        automation: "event-automation",
        status: "event-status",
        environment: "event-environment",
        alert: "event-alert",
    };
    return mapping[eventType] || "event-default";
}

function eventIcon(eventType) {
    const mapping = {
        speedtest: "activity",
        wan: "router",
        lighting: "lightbulb",
        automation: "automation",
        status: "info",
        environment: "thermometer",
        alert: "activity",
    };
    return svgIcon(mapping[eventType] || "info", "icon icon-sm");
}

function updateEvents(logs) {
    const container = getElement("events");
    if (!container) return;

    container.innerHTML = (logs || []).slice(0, 8).map((item) => {
        const timestamp = Number(item.timestamp || 0);
        const time = timestamp
            ? new Date(timestamp * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
            : "--";
        const message = item.event || item.lighting_status || "Unknown event";

        const normalizedMessage = String(message).toLowerCase();
        const severityClass =
            normalizedMessage.includes("offline") ||
            normalizedMessage.includes("critical") ||
            normalizedMessage.includes("hazardous")
                ? "event-severity-critical"
                : normalizedMessage.includes("failover") ||
                  normalizedMessage.includes("unhealthy") ||
                  normalizedMessage.includes("down")
                    ? "event-severity-warning"
                    : normalizedMessage.includes("moderate") ||
                      normalizedMessage.includes("advisory")
                        ? "event-severity-advisory"
                        : "event-severity-info";

        return `
            <div class="event ${eventClass(item.event_type)} ${severityClass}">
                <span class="event-marker"></span>
                <span class="event-icon">${eventIcon(item.event_type)}</span>
                <span class="event-time">${time}</span>
                <span class="event-message">${message}</span>
            </div>
        `;
    }).join("");
}

function updateSystemInformation(items) {
    const container = getElement("systemInformation");
    if (!container) return;

    const information = items || {};
    const preferredOrder = [
        "application",
        "database",
        "home_assistant",
        "peplink",
        "snmp",
        "speedtest",
        "wled",
        "version",
    ];

    const orderedKeys = [
        ...preferredOrder.filter((key) =>
            Object.prototype.hasOwnProperty.call(information, key)
        ),
        ...Object.keys(information).filter(
            (key) => !preferredOrder.includes(key)
        ),
    ];

    container.innerHTML = orderedKeys.map((key) => {
        const item = information[key];

        return `
            <div class="system-row">
                <span class="system-label">${item.label}</span>
                <span class="system-value system-${item.level || "neutral"}">${item.value}</span>
            </div>
        `;
    }).join("");
}



function setLightingMetricTone(id, tone) {
    const element = getElement(id);
    if (!element) return;

    element.classList.remove(
        "lighting-summary-metric-good",
        "lighting-summary-metric-info",
        "lighting-summary-metric-warning",
        "lighting-summary-metric-critical",
        "lighting-summary-metric-neutral"
    );
    element.classList.add(`lighting-summary-metric-${tone}`);
}

function updateLightingPage(data) {
    const lightingMode = data.lighting_label || "Unknown";
    const manualOverride = Boolean(data.manual_override);
    const lightingStatus = String(
        data.lighting_status || ""
    ).toLowerCase();

    setTextIfPresent("lightingPageMode", lightingMode);
    setTextIfPresent(
        "lightingPageControl",
        manualOverride ? "Manual Override" : "Automatic"
    );
    setTextIfPresent(
        "lightingPageOverride",
        manualOverride ? "Active" : "Inactive"
    );

    const wledInformation = data.system_information?.wled || {};
    const wledState = wledInformation.value || "Unknown";
    setTextIfPresent("lightingPageWled", wledState);

    const modeTone =
        lightingStatus === "offline"
            ? "critical"
            : lightingStatus === "failover" ||
              lightingStatus === "tmobile"
                ? "warning"
                : "good";

    const wledTone =
        String(wledInformation.level || "").toLowerCase() === "good"
            ? "info"
            : "critical";

    setLightingMetricTone("lightingModeMetric", modeTone);
    setLightingMetricTone(
        "lightingControlMetric",
        manualOverride ? "warning" : "good"
    );
    setLightingMetricTone("lightingWledMetric", wledTone);
    setLightingMetricTone(
        "lightingOverrideMetric",
        "warning"
    );
}

function updateHomeDomainTiles(data) {
    const airQuality = data.air_quality || {};
    const outdoorWeather = data.outdoor_weather || {};
    const environmentHealth = data.health?.environment || {};

    setTextIfPresent(
        "homeEnvironmentState",
        environmentHealth.state || "Unknown"
    );
    const environmentDot = getElement("homeEnvironmentStateDot");
    if (environmentDot) {
        const level = ["good", "warning", "critical"].includes(
            environmentHealth.level
        ) ? environmentHealth.level : "neutral";
        environmentDot.className =
            `executive-domain-status-dot executive-domain-status-${level}`;
    }
    setTextIfPresent(
        "homeAqiValue",
        airQuality.available && airQuality.aqi != null
            ? String(airQuality.aqi)
            : "--"
    );
    setTextIfPresent(
        "homeAqiCategory",
        airQuality.available
            ? airQuality.category || "Outdoor air"
            : "Air quality unavailable"
    );
    setTextIfPresent(
        "homeOutdoorTemperature",
        outdoorWeather.available &&
            outdoorWeather.temperature != null
            ? `${Number(outdoorWeather.temperature).toFixed(1)}°F`
            : "--°F"
    );
    setTextIfPresent(
        "homeCabinetTemperature",
        data.temperature == null
            ? "--°F"
            : `${Number(data.temperature).toFixed(1)}°F`
    );
    setTextIfPresent(
        "homeLightingMode",
        data.lighting_label || "Unknown"
    );
    setTextIfPresent(
        "homeLightingControl",
        data.manual_override ? "Manual" : "Automatic"
    );
    setTextIfPresent(
        "homeLightingOverride",
        data.manual_override ? "On" : "Off"
    );
}

function initializeWeatherRadar() {
    const frame = getElement("weatherRadarFrame");
    const shell = getElement("weatherRadarShell");
    if (!frame || !shell) return;

    let loaded = false;
    frame.addEventListener("load", () => {
        loaded = true;
        shell.classList.add("is-loaded");
        shell.classList.remove("is-unavailable");
    }, { once: true });

    window.setTimeout(() => {
        if (!loaded) shell.classList.add("is-unavailable");
    }, 15000);
}

function updateHomeRecentEvent(logs) {
    const target = getElement("homeRecentEvent");
    if (!target) return;

    const newest = Array.isArray(logs) ? logs[0] : null;
    if (!newest) {
        target.textContent = "No recent events";
        return;
    }

    target.textContent =
        newest.event || newest.lighting_status || "Recent activity";
}


let operationsLogs = [];
let operationsEventFilter = "all";


function relativeAge(timestamp) {
    const numericTimestamp = Number(timestamp || 0);
    if (!Number.isFinite(numericTimestamp) || numericTimestamp <= 0) {
        return "--";
    }

    const nowSeconds = Math.floor(Date.now() / 1000);
    const elapsed = Math.max(0, nowSeconds - numericTimestamp);

    if (elapsed < 10) return "Just now";
    if (elapsed < 60) return `${elapsed}s ago`;

    const minutes = Math.floor(elapsed / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function eventTimestamp(item) {
    const timestamp = Number(item?.timestamp || 0);
    return Number.isFinite(timestamp) ? timestamp : 0;
}

function classifyEventSeverity(message) {
    const normalized = String(message || "").toLowerCase();
    if (normalized.includes("offline") || normalized.includes("critical") || normalized.includes("hazardous")) return "critical";
    if (normalized.includes("failover") || normalized.includes("unhealthy") || normalized.includes("down") || normalized.includes("disconnected")) return "warning";
    if (normalized.includes("moderate") || normalized.includes("advisory")) return "advisory";
    return "info";
}

function updateOperationsSummary(data) {
    const information = data.system_information || {};
    const application = information.application || {};
    const database = information.database || {};
    const version = information.version || {};

    setTextIfPresent("operationsApplicationState", application.value || "Active");
    setTextIfPresent("operationsDatabaseState", database.value || "Unknown");
    setTextIfPresent("operationsVersion", version.value || "Unknown");
    setTextIfPresent("operationsRuntime", formatDuration(data.uptime_seconds));

    const badge = getElement("operationsOverallBadge");
    if (!badge) return;

    const values = Object.values(information);
    const critical = values.some((item) => item?.level === "critical");
    const warning = values.some((item) => item?.level === "warning");

    badge.className = critical
        ? "operations-domain-badge operations-domain-critical"
        : warning
            ? "operations-domain-badge operations-domain-warning"
            : "operations-domain-badge operations-domain-good";
    badge.textContent = critical ? "Attention Required" : warning ? "Degraded" : "Operational";
}

function updateOperationsAlertHealth(data) {
    if (!getElement("operationsAlertHealthCard")) return;
    const summary = data?.summary || {};
    const worker = data?.worker || {};
    const watchdog = data?.watchdog || {};
    const deliveryHealth = String(summary.delivery_health || "unknown");
    const deliveryLabels = {
        healthy: "Connected",
        retrying: "Retrying",
        degraded: "Degraded",
        unconfigured: "Not Configured",
    };
    setTextIfPresent("operationsAlertDelivery", deliveryLabels[deliveryHealth] || "Unknown");
    setTextIfPresent("operationsAlertWorker", worker.healthy ? "Active" : "Attention");
    setTextIfPresent("operationsAlertWatchdog", watchdog.healthy ? "Active" : "Attention");
    setTextIfPresent(
        "operationsAlertWatchdogAge",
        watchdog.updated_at ? `Heartbeat ${relativeAge(watchdog.updated_at)}` : "No watchdog heartbeat"
    );
    const active = Number(summary.active || 0);
    const pendingConditions = Number(summary.pending_conditions || 0);
    const pendingDeliveries = Number(summary.pending_deliveries || 0);
    setTextIfPresent("operationsAlertCounts", `${active} Active`);
    setTextIfPresent(
        "operationsAlertPending",
        `${pendingConditions} pending conditions • ${pendingDeliveries} queued deliveries`
    );
    setTextIfPresent(
        "operationsAlertLastDelivery",
        summary.last_delivered_at
            ? `Last delivered ${relativeAge(summary.last_delivered_at)}`
            : summary.last_delivery_error || "No alert delivered yet"
    );

    const badge = getElement("operationsAlertBadge");
    const degraded = !worker.healthy || !watchdog.healthy || ["degraded", "unconfigured"].includes(deliveryHealth);
    const warning = deliveryHealth === "retrying" || pendingDeliveries > 0;
    if (badge) {
        badge.className = degraded
            ? "operations-domain-badge operations-domain-critical"
            : warning || active > 0 || pendingConditions > 0
                ? "operations-domain-badge operations-domain-warning"
                : "operations-domain-badge operations-domain-good";
        badge.textContent = degraded ? "Attention Required" : warning ? "Retrying" : active > 0 ? "Active Alerts" : "Operational";
    }

    const container = getElement("operationsActiveAlerts");
    if (!container) return;
    const alerts = Array.isArray(data?.alerts)
        ? data.alerts.filter((item) => item.active || item.state === "pending" || item.delivery_status === "pending")
        : [];
    if (!alerts.length) {
        container.innerHTML = '<span class="operations-active-alerts-empty">No active alert conditions</span>';
        return;
    }
    container.innerHTML = alerts.map((item) => {
        const label = String(item.alert_id || "alert")
            .replaceAll(":", " · ")
            .replaceAll("_", " ");
        const status = item.delivery_status === "pending"
            ? `Delivery retry ${item.retry_count || 0}`
            : item.active ? "Active" : "Pending";
        return `<div class="operations-active-alert"><strong>${label}</strong><span>${status}</span></div>`;
    }).join("");
}

function filteredOperationsLogs() {
    return operationsEventFilter === "all"
        ? operationsLogs
        : operationsLogs.filter((item) => item.event_type === operationsEventFilter);
}

function updateOperationsActivity(logs) {
    const items = Array.isArray(logs) ? logs : [];
    const critical = items.filter(
        (item) =>
            classifyEventSeverity(
                item.event || item.lighting_status
            ) === "critical"
    ).length;
    const warning = items.filter(
        (item) =>
            classifyEventSeverity(
                item.event || item.lighting_status
            ) === "warning"
    ).length;

    setTextIfPresent("operationsEventCount", String(items.length));
    setTextIfPresent("operationsCriticalCount", String(critical));
    setTextIfPresent("operationsWarningCount", String(warning));

    const newest = [...items].sort(
        (left, right) =>
            eventTimestamp(right) - eventTimestamp(left)
    )[0];

    if (!newest) {
        setTextIfPresent("operationsLastEventAge", "No events");
        setTextIfPresent(
            "operationsLastEventMessage",
            "No recent operational events"
        );
        return;
    }

    const timestamp = eventTimestamp(newest);
    setTextIfPresent(
        "operationsLastEventAge",
        timestamp ? relativeAge(timestamp) : "--"
    );
    setTextIfPresent(
        "operationsLastEventMessage",
        newest.event ||
            newest.lighting_status ||
            "Recent activity"
    );
}

function renderOperationsLog() {
    const filtered = filteredOperationsLogs();
    updateEvents(filtered);
    const empty = getElement("operationsLogEmpty");
    if (empty) empty.classList.toggle("is-hidden", filtered.length > 0);
}

function setOperationsLogs(logs) {
    operationsLogs = Array.isArray(logs) ? logs : [];
    updateOperationsActivity(operationsLogs);
    renderOperationsLog();
}

function configureOperationsPage() {
    document.querySelectorAll(".operations-filter-button").forEach((button) => {
        button.addEventListener("click", () => {
            operationsEventFilter = button.dataset.eventFilter || "all";
            document.querySelectorAll(".operations-filter-button").forEach((candidate) => {
                candidate.classList.toggle("is-active", candidate === button);
            });
            renderOperationsLog();
        });
    });

    const refreshButton = getElement("operationsRefreshButton");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            refreshButton.disabled = true;
            refreshButton.classList.add("is-refreshing");
            try {
                await refresh();
            } finally {
                window.setTimeout(() => {
                    refreshButton.disabled = false;
                    refreshButton.classList.remove("is-refreshing");
                }, 350);
            }
        });
    }
}

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
    return response.json();
}

async function refresh() {
    try {
        const data = await fetchJson("/api/status");
        updateSystemBanner(data);
        updateHealth(data.health, data.air_quality);
        updateSpeedtest(data.speedtest);
        updateFooter(data);
        updateEnvironment(data);
        updateAirQuality(data.air_quality);
        updateOutdoorWeather(data.outdoor_weather);
        updateHomeDomainTiles(data);
        updateLightingPage(data);
        updateOperationsSummary(data);
        updateLightingControls(data);
        updateSnmpStatus(data.snmp);
        updateInternetRows(data.wans);
        updateSystemInformation(data.system_information);

        try {
            const logs = await fetchJson("/api/logs");
            updateEvents(logs);
            setOperationsLogs(logs);
            updateHomeRecentEvent(logs);
        } catch (error) {
            console.error("Unable to update Recent Events:", error);
        }
        if (getElement("operationsAlertHealthCard")) {
            try {
                updateOperationsAlertHealth(await fetchJson("/api/alerts"));
            } catch (error) {
                console.error("Unable to update alert health:", error);
                updateOperationsAlertHealth({
                    summary: {delivery_health: "degraded"},
                    worker: {healthy: false}, watchdog: {healthy: false}, alerts: [],
                });
            }
        }
    } catch (error) {
        console.error("Dashboard status refresh failed:", error);
    }
}

async function setLight(status) {
    try {
        await fetchJson(`/api/lights/${status}`);
        await refresh();
    } catch (error) {
        console.error(`Unable to set lighting status "${status}":`, error);
    }
}

async function clearOverride() {
    try {
        await fetchJson("/api/lights/auto");
        await refresh();
    } catch (error) {
        console.error("Unable to return lighting to automatic mode:", error);
    }
}

function registerLightingControls() {
    document.querySelectorAll("[data-light-status]").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.dataset.lightStatus) setLight(button.dataset.lightStatus);
        });
    });
    getElement("returnToAutoButton")?.addEventListener("click", clearOverride);
}

function initializeDashboard() {
    registerLightingControls();
    configureOperationsPage();
    initializeWeatherRadar();
    refresh();
    refreshSecurity();
    refreshNetworking();
    initializeNetworkingControls();
    initializeNetworkingSprint5();
    window.setInterval(refresh, getPollSeconds() * 1000);
    window.setInterval(refreshSecurity, getPollSeconds() * 1000);
    window.setInterval(refreshNetworking, getPollSeconds() * 1000);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDashboard);
} else {
    initializeDashboard();
}

function securityDisplayAge(epoch) {
    if (!epoch) return "No activity";
    return relativeAge(epoch);
}

function securityMetric(label, value) {
    return `<div class="security-camera-metric"><span>${label}</span><strong>${value}</strong></div>`;
}

function renderSecurity(data) {
    const cameras = Array.isArray(data?.cameras) ? data.cameras : [];
    const hasConfiguredCount = data?.configured_count !== undefined
        && Number.isFinite(Number(data.configured_count));
    if (hasConfiguredCount || cameras.length > 0) {
        const configuredCount = hasConfiguredCount
            ? Number(data.configured_count)
            : cameras.length;
        setTextIfPresent(
            "homeSecurityCameraCount",
            `${configuredCount} ${configuredCount === 1 ? "Camera" : "Cameras"}`
        );
    }

    const grid = getElement("securityCameraGrid");
    if (!grid) return;
    const summary = data?.summary || {};
    setTextIfPresent("securityOnline", `${summary.online ?? 0} / ${summary.total ?? 0}`);
    setTextIfPresent("securityMotion", `${summary.motion_enabled ?? 0} / ${summary.motion_capable ?? 0}`);
    setTextIfPresent("securityAlerts", `${summary.alerts ?? 0}`);
    setTextIfPresent("securityAlertDetail", summary.critical ? `${summary.critical} critical` : summary.attention ? `${summary.attention} need attention` : "No active exceptions");
    setTextIfPresent(
    "securityLastEventName",
    summary.last_event_label || "No recent activity"
);

setTextIfPresent(
    "securityLastEvent",
    summary.last_event_epoch
        ? securityDisplayAge(summary.last_event_epoch)
        : "Waiting for camera activity"
);
    setTextIfPresent("securityOnlineDetail", data.available ? "Home Assistant connected" : "Integration degraded");

    const badge = getElement("securityDomainBadge");
    if (badge) {
        badge.className = `security-domain-badge is-${data.overall || "critical"}`;
        badge.textContent = data.overall === "healthy" ? "All Systems Normal" : data.overall === "warning" ? "Attention Required" : "Critical Attention";
    }

    grid.innerHTML = cameras.map((camera) => {
        const motion = camera.motion_enabled === null ? "Unknown" : camera.motion_enabled ? "Enabled" : "Disabled";
        const battery = camera.battery_percent === null ? "--" : `${camera.battery_percent}%`;
        const metrics = [
            securityMetric("Battery", battery),
            securityMetric("Motion", motion),
            securityMetric("Last Activity", securityDisplayAge(camera.last_activity_epoch)),
            securityMetric("Camera", camera.available ? "Online" : "Offline"),
        ];
        if (camera.has_light) metrics.push(securityMetric("Light", camera.light_state === "on" ? "On" : "Off"));
        if (camera.has_siren) metrics.push(securityMetric("Siren", camera.siren_state === "on" ? "Active" : "Ready"));
        const issues = camera.issues?.length ? `<div class="security-camera-issues">${camera.issues.join(" • ")}</div>` : "";
        return `<article class="security-camera-card is-${camera.health}"><div class="security-camera-head"><div class="security-camera-title"><span class="security-camera-dot"></span>${camera.name}</div><span class="security-camera-state">${camera.health_label}</span></div><div class="security-camera-metrics">${metrics.join("")}</div>${issues}</article>`;
    }).join("");
    getElement("securityCameraEmpty")?.classList.toggle("is-hidden", cameras.length > 0);
}

async function refreshSecurity() {
    if (!getElement("securityCameraGrid") && !getElement("homeSecurityCameraCount")) return;
    try {
        renderSecurity(await fetchJson("/api/security/cameras"));
    } catch (error) {
        console.error("Security refresh failed:", error);
        renderSecurity({available:false, overall:"critical", summary:{}, cameras:[]});
    }
}

/* RC-001 v2.1.0 RC2 Sprint 1 — Networking framework */
function networkingNode(label, role, status = "configured") {
    const safeStatus = ["online", "offline", "configured", "warning"].includes(status) ? status : "configured";
    return `<div class="networking-node networking-node-${role} is-${safeStatus}"><span class="networking-node-dot"></span><strong>${label}</strong></div>`;
}

let networkingLatestPayload = null;
let networkingPreviousStatuses = new Map();

function renderNetworking(data) {
    networkingLatestPayload = data;
    const topologyElement = getElement("networkingTopology");
    if (!topologyElement) return;
    const summary = data?.summary || {};
    const topology = data?.topology || {};
    const wans = Array.isArray(topology.wans) ? topology.wans : [];

    setTextIfPresent("networkingTotal", summary.total ?? 0);
    setTextIfPresent("networkingInfrastructure", summary.infrastructure ?? 0);
    setTextIfPresent("networkingSecurity", summary.security ?? 0);
    setTextIfPresent("networkingClients", summary.clients ?? 0);
    setTextIfPresent("networkingUnknown", summary.unknown ?? 0);
    setTextIfPresent("networkingOffline", summary.offline ?? 0);
    setTextIfPresent("networkingUpdated", data?.updated_at ? `Updated ${relativeAge(data.updated_at)}` : "Waiting");

    getElement("networkingUnknownCard")?.classList.toggle("has-warning", Number(summary.unknown || 0) > 0);
    getElement("networkingOfflineCard")?.classList.toggle("has-critical", Number(summary.offline || 0) > 0);

    renderNetworkingDeviceSections(data);

    renderNetworkingSprint3(data);
    networkingAnimateStatusChanges(data);

    if (renderNetworkingTopologyEngine(data)) {
        renderNetworkingInfrastructureIntelligence(data);
        return;
    }

    const wanNodes = wans.map((wan) => networkingNode(wan.name || "WAN", "wan", wan.status)).join("");
    topologyElement.innerHTML = `
        <div class="networking-topology-label">${topology.internet_label || "Internet Sources"}</div>
        <div class="networking-wan-row">${wanNodes}</div>
        <div class="networking-connector networking-connector-merge" aria-hidden="true"><span></span><span></span><span></span></div>
        ${networkingNode(topology.router?.name || "Peplink B One", "router", topology.router?.status)}
        <div class="networking-connector networking-connector-vertical" aria-hidden="true"></div>
        ${networkingNode(topology.mesh?.name || "TP-Link Deco Mesh", "mesh", topology.mesh?.status)}
        <div class="networking-topology-groups" aria-label="Device groups"><span>Infrastructure (${topology.group_counts?.infrastructure ?? summary.infrastructure ?? 0})</span><span>Security (${topology.group_counts?.security ?? summary.security ?? 0})</span><span>Clients (${topology.group_counts?.clients ?? summary.clients ?? 0})</span></div>
        <div class="networking-framework-note">Logical topology • live device discovery follows in later RC2 sprints</div>`;
}

async function refreshNetworking() {
    if (!getElement("networkingTopology")) return;
    try {
        renderNetworking(await fetchJson("/api/networking"));
    } catch (error) {
        console.error("Networking refresh failed:", error);
        const element = getElement("networkingTopology");
        if (element) element.innerHTML = '<div class="empty-state">Networking framework is unavailable.</div>';
    }
}

/* RC-001 v2.1.0 RC2 Sprint 2 — Infrastructure and Security */
function networkingEscape(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function networkingDeviceCard(device, kind) {
    const status = ["online", "offline", "configured", "warning"].includes(device.status)
        ? device.status
        : "configured";
    const address = device.address ? networkingEscape(device.address) : "Address unavailable";
    const connection = networkingEscape(device.connection || "Network");
    const notes = networkingEscape(device.notes || "");
    const battery = device.battery_percent === null || device.battery_percent === undefined
        ? ""
        : `<div class="networking-device-fact"><span>Battery</span><strong>${device.battery_percent}%</strong></div>`;
    const motion = device.motion_enabled === null || device.motion_enabled === undefined
        ? ""
        : `<div class="networking-device-fact"><span>Motion</span><strong>${device.motion_enabled ? "Enabled" : "Disabled"}</strong></div>`;
    const activity = device.last_activity_epoch
        ? `<div class="networking-device-fact"><span>Last Activity</span><strong>${securityDisplayAge(device.last_activity_epoch)}</strong></div>`
        : "";
    const issues = Array.isArray(device.issues) && device.issues.length
        ? `<div class="networking-device-issues">${device.issues.map(networkingEscape).join(" • ")}</div>`
        : "";

    return `
        <article tabindex="0" role="button" data-networking-device-id="${networkingEscape(device.id || device.mac || device.ip || device.name)}" class="card networking-device-card networking-device-selectable is-${status} networking-device-${kind}">
            <div class="networking-device-head">
                <span class="networking-device-status-dot"></span>
                <div>
                    <strong>${networkingEscape(device.name || "Device")}</strong>
                    <small>${networkingEscape(device.status_label || status)}</small>
                </div>
            </div>
            <div class="networking-device-facts">
                <div class="networking-device-fact"><span>Address</span><strong>${address}</strong></div>
                <div class="networking-device-fact"><span>Connection</span><strong>${connection}</strong></div>
                ${battery}${motion}${activity}
            </div>
            ${notes ? `<p class="networking-device-notes">${notes}</p>` : ""}
            ${issues}
        </article>`;
}

function renderNetworkingDeviceSections(data) {
    const infrastructure = Array.isArray(data?.infrastructure) ? data.infrastructure : [];
    const security = Array.isArray(data?.security) ? data.security : [];

    const infrastructureGrid = getElement("networkingInfrastructureGrid");
    if (infrastructureGrid) {
        infrastructureGrid.innerHTML = infrastructure
            .map((device) => networkingDeviceCard(device, "infrastructure"))
            .join("");
    }
    getElement("networkingInfrastructureEmpty")?.classList.toggle(
        "is-hidden",
        infrastructure.length > 0
    );

    const securityGrid = getElement("networkingSecurityGrid");
    if (securityGrid) {
        securityGrid.innerHTML = security
            .map((device) => networkingDeviceCard(device, "security"))
            .join("");
    }
    getElement("networkingSecurityEmpty")?.classList.toggle(
        "is-hidden",
        security.length > 0
    );
}

/* RC-001 v2.1.0 RC2 Sprint 3 — Device discovery and inventory */
function networkingCategoryBadge(category, label) {
    return `<span class="networking-category-badge is-${networkingEscape(category)}">${networkingEscape(label)}</span>`;
}

function renderNetworkingClients(data) {
    const clients = Array.isArray(data?.clients) ? data.clients : [];
    const summary = data?.summary || {};
    const categories = summary.categories || {};
    const labels = data?.category_labels || {};

    setTextIfPresent("networkingActiveClients", `${summary.active_clients ?? 0} active`);
    setTextIfPresent("networkingNewDevices", `${summary.new ?? 0} new`);
    setTextIfPresent(
        "networkingDiscoveryDetail",
        data?.discovery?.available
            ? `${data.discovery.active_count ?? 0} active of ${data.discovery.client_count ?? 0} Peplink clients`
            : "Peplink client discovery unavailable"
    );

    const categorySummary = getElement("networkingCategorySummary");
    if (categorySummary) {
        categorySummary.innerHTML = Object.entries(categories)
            .filter(([, count]) => Number(count) > 0)
            .map(([category, count]) =>
                `<span>${networkingEscape(labels[category] || category)} <strong>${count}</strong></span>`
            )
            .join("");
    }

    const grid = getElement("networkingClientGrid");
    if (grid) {
        grid.innerHTML = clients.map((device) => {
            const badge = device.is_new
                ? '<span class="networking-new-badge">NEW</span>'
                : "";
            const vendor = device.vendor
                ? `<div class="networking-device-fact"><span>Vendor</span><strong>${networkingEscape(device.vendor)}</strong></div>`
                : "";
            const signal = device.signal_dbm !== null && device.signal_dbm !== undefined
                ? `<div class="networking-device-fact"><span>Signal</span><strong>${device.signal_dbm} dBm</strong></div>`
                : "";
            return `
                <article tabindex="0" role="button" data-networking-device-id="${networkingEscape(device.id || device.mac || device.ip || device.name)}" class="card networking-device-card networking-device-selectable is-${device.status || "configured"}">
                    <div class="networking-device-head">
                        <span class="networking-device-status-dot"></span>
                        <div><strong>${networkingEscape(device.name)}</strong><small>${networkingEscape(device.status_label || "Unknown")}</small></div>
                        ${badge}
                    </div>
                    <div class="networking-device-category-row">
                        ${networkingCategoryBadge(device.category, device.category_label)}
                        <small>${networkingEscape(device.classification_source || "unclassified")}</small>
                    </div>
                    <div class="networking-device-facts">
                        <div class="networking-device-fact"><span>Address</span><strong>${networkingEscape(device.ip || "--")}</strong></div>
                        <div class="networking-device-fact"><span>Connection</span><strong>${networkingEscape(device.connection || "Other")}</strong></div>
                        ${vendor}${signal}
                    </div>
                </article>`;
        }).join("");
    }
    getElement("networkingClientEmpty")?.classList.toggle("is-hidden", clients.length > 0);
}

function renderNetworkingInventory(data) {
    const inventory = Array.isArray(data?.inventory) ? data.inventory : [];
    setTextIfPresent("networkingInventoryCount", `${inventory.length} devices`);

    const body = getElement("networkingInventoryBody");
    if (body) {
        body.innerHTML = inventory.map((device) => `
            <tr class="${device.is_new ? "is-new" : ""}">
                <td><strong>${networkingEscape(device.name)}</strong>${device.is_new ? '<span class="networking-new-badge">NEW</span>' : ""}<small>${networkingEscape(device.hostname || "")}</small></td>
                <td>${networkingEscape(device.ip || "--")}</td>
                <td><code>${networkingEscape(device.mac || "--")}</code></td>
                <td>${networkingCategoryBadge(device.category, device.category_label)}</td>
                <td>${networkingEscape(device.connection || "Other")}</td>
                <td><span class="networking-table-status is-${networkingEscape(device.status || "configured")}">${networkingEscape(device.status_label || "Unknown")}</span></td>
            </tr>`).join("");
    }
    getElement("networkingInventoryEmpty")?.classList.toggle("is-hidden", inventory.length > 0);
}

function renderNetworkingSprint3(data) {
    renderNetworkingClients(data);
    renderNetworkingInventory(data);
}

/* RC-001 v2.1.0 RC2 Sprint 4 — Search, filters, sorting, registry */
const networkingInventoryState={devices:[],search:"",category:"all",status:"all",connection:"all",sortKey:"name",sortDirection:"asc"};
function networkingNormalize(v){return String(v??"").trim().toLowerCase()}
function networkingSortValue(d,k){if(k==="ip")return String(d.ip||"").split(".").reduce((t,p)=>(t*256)+Number(p||0),0);if(k==="status")return d.status==="online"?0:1;return networkingNormalize(d[k])}
function networkingFilteredInventory(){const s=networkingInventoryState,q=networkingNormalize(s.search);return s.devices.filter(d=>{const h=[d.name,d.hostname,d.ip,d.mac,d.vendor,d.category_label,d.connection].map(networkingNormalize).join(" ");return(!q||h.includes(q))&&(s.category==="all"||d.category===s.category)&&(s.status==="all"||d.status===s.status)&&(s.connection==="all"||networkingNormalize(d.connection_type||d.connection)===s.connection)}).sort((a,b)=>{const x=networkingSortValue(a,s.sortKey),y=networkingSortValue(b,s.sortKey),c=typeof x==="number"&&typeof y==="number"?x-y:String(x).localeCompare(String(y),undefined,{numeric:true,sensitivity:"base"});return s.sortDirection==="asc"?c:-c})}
function networkingPopulateFilterOptions(devices){const cats=[...new Set(devices.map(d=>d.category).filter(Boolean))].sort(),conns=[...new Set(devices.map(d=>networkingNormalize(d.connection_type||d.connection)).filter(Boolean))].sort(),cs=getElement("networkingCategoryFilter"),xs=getElement("networkingConnectionFilter");if(cs){const v=cs.value||"all";cs.innerHTML=['<option value="all">All categories</option>',...cats.map(c=>`<option value="${networkingEscape(c)}">${networkingEscape(devices.find(d=>d.category===c)?.category_label||c)}</option>`)].join("");cs.value=cats.includes(v)?v:"all"}if(xs){const v=xs.value||"all";xs.innerHTML=['<option value="all">All connections</option>',...conns.map(c=>`<option value="${networkingEscape(c)}">${networkingEscape(c.replace(/\b\w/g,m=>m.toUpperCase()))}</option>`)].join("");xs.value=conns.includes(v)?v:"all"}}
function networkingInventoryRow(d){const action=d.mac?`<button type="button" class="networking-registry-button" data-networking-edit="${networkingEscape(d.mac)}">${d.registered?"Edit":"Name"}</button>`:"";return `<tr tabindex="0" data-networking-device-id="${networkingEscape(d.id||d.mac||d.ip||d.name)}" class="networking-inventory-device-row ${d.is_new?"is-new":""}"><td><strong>${networkingEscape(d.name)}</strong>${d.is_new?'<span class="networking-new-badge">NEW</span>':""}<small>${networkingEscape(d.hostname||"")}</small></td><td>${networkingEscape(d.ip||"--")}</td><td><code>${networkingEscape(d.mac||"--")}</code></td><td>${networkingCategoryBadge(d.category,d.category_label)}</td><td>${networkingEscape(d.connection||"Other")}</td><td><span class="networking-table-status is-${networkingEscape(d.status||"configured")}">${networkingEscape(d.status_label||"Unknown")}</span></td><td>${action}</td></tr>`}
function renderNetworkingFilteredInventory(){const rows=networkingFilteredInventory(),body=getElement("networkingInventoryBody");if(body)body.innerHTML=rows.map(networkingInventoryRow).join("");setTextIfPresent("networkingInventoryCount",`${rows.length} of ${networkingInventoryState.devices.length} devices`);getElement("networkingInventoryEmpty")?.classList.toggle("is-hidden",rows.length>0);document.querySelectorAll("[data-networking-edit]").forEach(b=>b.addEventListener("click",()=>networkingOpenRegistryEditor(b.dataset.networkingEdit)))}
function renderNetworkingInventory(data){networkingInventoryState.devices=Array.isArray(data?.inventory)?data.inventory:[];networkingPopulateFilterOptions(networkingInventoryState.devices);renderNetworkingFilteredInventory()}
function networkingOpenRegistryEditor(mac){const d=networkingInventoryState.devices.find(x=>networkingNormalize(x.mac)===networkingNormalize(mac)),dialog=getElement("networkingRegistryDialog");if(!d||!dialog)return;getElement("networkingRegistryMac").value=d.mac||"";getElement("networkingRegistryName").value=d.name_source==="registry"?d.name:"";getElement("networkingRegistryCategory").value=d.category||"unknown";getElement("networkingRegistryNotes").value=d.notes||"";setTextIfPresent("networkingRegistryDeviceContext",`${d.hostname||d.name} • ${d.ip||"No address"}`);getElement("networkingRegistryDelete").hidden=!d.registered;getElement("networkingRegistryFeedback").textContent="";dialog.showModal()}
async function networkingSaveRegistry(){const mac=getElement("networkingRegistryMac")?.value,name=getElement("networkingRegistryName")?.value,category=getElement("networkingRegistryCategory")?.value,notes=getElement("networkingRegistryNotes")?.value,feedback=getElement("networkingRegistryFeedback");if(!mac||!name||!category){if(feedback)feedback.textContent="Name and category are required.";return}try{const r=await fetch(`/api/networking/registry/${encodeURIComponent(mac)}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,category,notes})}),p=await r.json();if(!r.ok)throw new Error(p.error||`HTTP ${r.status}`);getElement("networkingRegistryDialog")?.close();await refreshNetworking()}catch(e){if(feedback)feedback.textContent=`Unable to save: ${e.message}`}}
async function networkingDeleteRegistry(){const mac=getElement("networkingRegistryMac")?.value,feedback=getElement("networkingRegistryFeedback");if(!mac)return;try{const r=await fetch(`/api/networking/registry/${encodeURIComponent(mac)}`,{method:"DELETE"}),p=await r.json();if(!r.ok)throw new Error(p.error||`HTTP ${r.status}`);getElement("networkingRegistryDialog")?.close();await refreshNetworking()}catch(e){if(feedback)feedback.textContent=`Unable to remove: ${e.message}`}}
function initializeNetworkingControls(){const search=getElement("networkingSearch"),cat=getElement("networkingCategoryFilter"),status=getElement("networkingStatusFilter"),conn=getElement("networkingConnectionFilter"),clear=getElement("networkingClearFilters");search?.addEventListener("input",()=>{networkingInventoryState.search=search.value;renderNetworkingFilteredInventory()});cat?.addEventListener("change",()=>{networkingInventoryState.category=cat.value;renderNetworkingFilteredInventory()});status?.addEventListener("change",()=>{networkingInventoryState.status=status.value;renderNetworkingFilteredInventory()});conn?.addEventListener("change",()=>{networkingInventoryState.connection=conn.value;renderNetworkingFilteredInventory()});clear?.addEventListener("click",()=>{Object.assign(networkingInventoryState,{search:"",category:"all",status:"all",connection:"all"});if(search)search.value="";if(cat)cat.value="all";if(status)status.value="all";if(conn)conn.value="all";renderNetworkingFilteredInventory()});document.querySelectorAll("[data-networking-sort]").forEach(b=>b.addEventListener("click",()=>{const k=b.dataset.networkingSort;networkingInventoryState.sortDirection=networkingInventoryState.sortKey===k&&networkingInventoryState.sortDirection==="asc"?"desc":"asc";networkingInventoryState.sortKey=k;renderNetworkingFilteredInventory()}));getElement("networkingRegistrySave")?.addEventListener("click",networkingSaveRegistry);getElement("networkingRegistryDelete")?.addEventListener("click",networkingDeleteRegistry);getElement("networkingRegistryCancel")?.addEventListener("click",()=>getElement("networkingRegistryDialog")?.close())}


/* RC-001 v2.1.0 RC2 Sprint 5 — Device details drawer and live status animations */
function networkingAllDevices() {
    const data = networkingLatestPayload || {};
    const topologyNodes = Array.isArray(data?.topology?.nodes) ? data.topology.nodes.map((node) => ({
        ...node,
        name: node.label,
        category_label: node.type ? node.type.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Topology",
        connection: node.type === "wan" ? "WAN" : "Logical topology",
    })) : [];
    return [
        ...(Array.isArray(data.infrastructure) ? data.infrastructure : []),
        ...(Array.isArray(data.security) ? data.security : []),
        ...(Array.isArray(data.clients) ? data.clients : []),
        ...topologyNodes,
    ];
}
function networkingFindDevice(id) {
    const wanted = networkingNormalize(id);
    return networkingAllDevices().find((device) => [device.id, device.mac, device.ip, device.address, device.name, device.label].some((value) => networkingNormalize(value) === wanted));
}
function networkingDrawerFact(label, value) {
    if (value === null || value === undefined || value === "") return "";
    return `<div><span>${networkingEscape(label)}</span><strong>${networkingEscape(value)}</strong></div>`;
}
function networkingOpenDeviceDrawer(id) {
    const device = networkingFindDevice(id);
    const drawer = getElement("networkingDeviceDrawer");
    if (!device || !drawer) return;
    const status = networkingNormalize(device.status || device.health || "configured");
    setTextIfPresent("networkingDrawerTitle", device.name || device.label || "Device");
    setTextIfPresent("networkingDrawerSubtitle", `${device.category_label || device.type || "Network device"} • Live RC-001 telemetry`);
    const statusBox = getElement("networkingDrawerStatus");
    if (statusBox) {
        statusBox.className = `networking-drawer-status is-${status}`;
        statusBox.innerHTML = `<span class="networking-live-orb"></span><strong>${networkingEscape(device.status_label || device.health_label || status || "Unknown")}</strong><small>${device.active === false ? "Inactive client" : "Live status"}</small>`;
    }
    const facts = [
        ["IP address", device.ip || device.address], ["MAC address", device.mac], ["Hostname", device.hostname],
        ["Vendor", device.vendor], ["Connection", device.connection || device.connection_type], ["Category", device.category_label || device.type],
        ["Signal", device.signal_dbm === null || device.signal_dbm === undefined ? null : `${device.signal_dbm} dBm`],
        ["Battery", device.battery_percent === null || device.battery_percent === undefined ? null : `${device.battery_percent}%`],
        ["Last activity", device.last_activity_epoch ? securityDisplayAge(device.last_activity_epoch) : null],
        ["Registry", device.registered === undefined ? null : device.registered ? "Registered" : "Automatic discovery"],
    ];
    const factBox = getElement("networkingDrawerFacts");
    if (factBox) factBox.innerHTML = facts.map(([label,value]) => networkingDrawerFact(label,value)).join("") || networkingDrawerFact("Details", "No additional telemetry available");
    const metrics = Object.entries(device.metrics || {}).filter(([,value]) => value !== null && value !== undefined);
    const metricBox = getElement("networkingDrawerMetrics");
    if (metricBox) metricBox.innerHTML = metrics.length ? `<h4>Live Metrics</h4><div>${metrics.map(([key,value]) => networkingDrawerFact(key.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase()), value)).join("")}</div>` : "";
    const notes = getElement("networkingDrawerNotes");
    if (notes) { notes.textContent = device.notes || (Array.isArray(device.issues) ? device.issues.join(" • ") : ""); notes.hidden = !notes.textContent; }
    const registry = getElement("networkingDrawerRegistry");
    if (registry) { registry.hidden = !device.mac; registry.dataset.mac = device.mac || ""; }
    drawer.classList.add("is-open"); drawer.setAttribute("aria-hidden", "false"); document.body.classList.add("networking-drawer-open");
    getElement("networkingDrawerClose")?.focus();
}
function networkingCloseDeviceDrawer() {
    const drawer = getElement("networkingDeviceDrawer");
    if (!drawer) return;
    drawer.classList.remove("is-open"); drawer.setAttribute("aria-hidden", "true"); document.body.classList.remove("networking-drawer-open");
}
function networkingAnimateStatusChanges(data) {
    const current = new Map();
    [ ...(data?.infrastructure || []), ...(data?.security || []), ...(data?.clients || []) ].forEach((device) => {
        const id = networkingNormalize(device.id || device.mac || device.ip || device.name);
        const status = networkingNormalize(device.status || "configured");
        current.set(id, status);
        if (networkingPreviousStatuses.has(id) && networkingPreviousStatuses.get(id) !== status) {
            document.querySelectorAll(`[data-networking-device-id="${CSS.escape(device.id || device.mac || device.ip || device.name)}"]`).forEach((element) => {
                element.classList.remove("networking-status-changed"); void element.offsetWidth; element.classList.add("networking-status-changed");
            });
        }
    });
    networkingPreviousStatuses = current;
}
function initializeNetworkingSprint5() {
    document.addEventListener("click", (event) => {
        if (event.target.closest("[data-networking-edit]")) return;
        const target = event.target.closest("[data-networking-device-id]");
        if (target) networkingOpenDeviceDrawer(target.dataset.networkingDeviceId);
    });
    document.addEventListener("keydown", (event) => {
        const target = event.target.closest?.("[data-networking-device-id]");
        if (target && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); networkingOpenDeviceDrawer(target.dataset.networkingDeviceId); }
        if (event.key === "Escape") networkingCloseDeviceDrawer();
    });
    getElement("networkingDrawerClose")?.addEventListener("click", networkingCloseDeviceDrawer);
    getElement("networkingDrawerBackdrop")?.addEventListener("click", networkingCloseDeviceDrawer);
    getElement("networkingDrawerRegistry")?.addEventListener("click", (event) => { const mac=event.currentTarget.dataset.mac; networkingCloseDeviceDrawer(); if(mac) networkingOpenRegistryEditor(mac); });
}

/* RC-001 v2.1.0 RC2 Sprint 5.1-5.2 — Topology engine and infrastructure intelligence */
function networkingTopologyMetric(label, value) {
    if (value === null || value === undefined || value === "") return "";
    return `<span><small>${networkingEscape(label)}</small><strong>${networkingEscape(value)}</strong></span>`;
}

function networkingRichTopologyNode(node) {
    const metrics = node.metrics || {};
    const metricEntries = Object.entries(metrics)
        .filter(([, value]) => value !== null && value !== undefined)
        .slice(0, 3)
        .map(([key, value]) => networkingTopologyMetric(
            key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()),
            value
        ))
        .join("");

    return `
        <article tabindex="0" role="button" data-networking-device-id="${networkingEscape(node.id || node.label)}" class="networking-rich-node networking-device-selectable is-${networkingEscape(node.status || "configured")}">
            <div class="networking-rich-node-head">
                <span class="networking-device-status-dot"></span>
                <div>
                    <strong>${networkingEscape(node.label)}</strong>
                    <small>${networkingEscape(node.status_label || "Configured")}</small>
                </div>
            </div>
            ${metricEntries ? `<div class="networking-rich-node-metrics">${metricEntries}</div>` : ""}
        </article>`;
}

function renderNetworkingTopologyEngine(data) {
    const topologyElement = getElement("networkingTopology");
    const topology = data?.topology || {};
    const nodes = Array.isArray(topology.nodes) ? topology.nodes : [];
    if (!topologyElement || !nodes.length) return false;

    const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));
    const wans = nodes.filter((node) => node.type === "wan");
    const router = nodes.find((node) => node.type === "router");
    const mesh = nodes.find((node) => node.type === "mesh");
    const infrastructure = nodes.filter((node) => node.type === "infrastructure");
    const securityGroup = byId.security_group;
    const clientGroup = byId.client_group;
    const categories = nodes.filter((node) => node.type === "category");

    topologyElement.innerHTML = `
        <div class="networking-topology-label">Internet Sources</div>
        <div class="networking-wan-row">
            ${wans.map(networkingRichTopologyNode).join("")}
        </div>
        <div class="networking-connector networking-connector-merge" aria-hidden="true"><span></span><span></span><span></span></div>
        ${router ? networkingRichTopologyNode(router) : ""}
        <div class="networking-connector networking-connector-vertical" aria-hidden="true"></div>
        ${mesh ? networkingRichTopologyNode(mesh) : ""}
        <div class="networking-topology-branch-grid">
            <section>
                <h3>Infrastructure</h3>
                <div class="networking-topology-child-list">
                    ${infrastructure.map(networkingRichTopologyNode).join("")}
                </div>
            </section>
            <section>
                <h3>Security</h3>
                ${securityGroup ? networkingRichTopologyNode(securityGroup) : ""}
            </section>
            <section>
                <h3>Clients</h3>
                ${clientGroup ? networkingRichTopologyNode(clientGroup) : ""}
                <div class="networking-topology-category-list">
                    ${categories.map(networkingRichTopologyNode).join("")}
                </div>
            </section>
        </div>
        <div class="networking-framework-note">
            ${topology.summary?.node_count ?? nodes.length} topology nodes •
            ${topology.summary?.edge_count ?? 0} verified logical relationships
        </div>`;

    return true;
}

function renderNetworkingInfrastructureIntelligence(data) {
    const infrastructure = Array.isArray(data?.infrastructure) ? data.infrastructure : [];
    const grid = getElement("networkingInfrastructureGrid");
    if (!grid) return;

    grid.innerHTML = infrastructure.map((device) => {
        const metrics = device.metrics || {};
        const metricMarkup = Object.entries(metrics)
            .filter(([, value]) => value !== null && value !== undefined)
            .map(([key, value]) => `
                <div class="networking-device-fact">
                    <span>${networkingEscape(key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()))}</span>
                    <strong>${networkingEscape(value)}</strong>
                </div>`)
            .join("");

        return `
            <article tabindex="0" role="button" data-networking-device-id="${networkingEscape(device.id || device.ip || device.name)}" class="card networking-device-card networking-device-selectable networking-intelligent-card is-${device.status || "configured"}">
                <div class="networking-device-head">
                    <span class="networking-device-status-dot"></span>
                    <div>
                        <strong>${networkingEscape(device.name)}</strong>
                        <small>${networkingEscape(device.status_label || "Configured")}</small>
                    </div>
                </div>
                <div class="networking-device-facts">
                    <div class="networking-device-fact"><span>Address</span><strong>${networkingEscape(device.address || "Address unavailable")}</strong></div>
                    <div class="networking-device-fact"><span>Connection</span><strong>${networkingEscape(device.connection || "Network")}</strong></div>
                    ${metricMarkup}
                </div>
                ${device.notes ? `<p class="networking-device-notes">${networkingEscape(device.notes)}</p>` : ""}
            </article>`;
    }).join("");

    getElement("networkingInfrastructureEmpty")?.classList.toggle(
        "is-hidden",
        infrastructure.length > 0
    );
}
