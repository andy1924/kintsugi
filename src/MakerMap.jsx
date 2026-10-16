import React, { useEffect, useRef, useState } from "react";
import { LocateFixed, MapPin, ArrowUpRight } from "lucide-react";
import { api } from "./api";
import { approximateLocation as approximate, currentArea } from "./location";
import "leaflet/dist/leaflet.css";
import "./maker-map.css";

const INDIA = [22.5, 79];
const coords = (point) => [point.latitude, point.longitude];
const communities = {
  independent: "Independent business",
  women_led: "Women-led workroom",
  community_enterprise: "Community enterprise",
};

function useLocation(onLocation) {
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  function locate() {
    setError("");
    if (!navigator.geolocation || !window.isSecureContext) {
      setError(
        "Location needs a secure connection and a supported browser. You can choose an area on the map instead.",
      );
      return;
    }
    setLocating(true);
    currentArea(navigator.geolocation).then(
      (point) => {
        if (!mounted.current) return;
        setLocating(false);
        onLocation(point);
      },
      (reason) => {
        if (!mounted.current) return;
        setLocating(false);
        setError(
          reason.code === 1
            ? "Location permission is off. Allow it in your browser, or choose an area on the map."
            : "We couldn’t find your location. Try again, or choose an area on the map.",
        );
      },
    );
  }
  return { locate, locating, error };
}

function MapCanvas({ point, makers = [], onPick, onChoose, editor = false }) {
  const host = useRef(null);
  const map = useRef(null);
  const leaflet = useRef(null);
  const layer = useRef(null);
  const handlers = useRef({ onPick, onChoose });
  handlers.current = { onPick, onChoose };
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let observer;
    Promise.all([import("leaflet"), api("/network/map-config")])
      .then(([module, config]) => {
        if (!active) return;
        const L = module.default;
        leaflet.current = L;
        const instance = L.map(host.current, {
          scrollWheelZoom: false,
        }).setView(INDIA, 4);
        map.current = instance;
        L.tileLayer(config.tile_url, {
          maxZoom: 18,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        })
          .on("tileerror", () => {
            if (active)
              setError(
                "Some map tiles couldn’t load. You can still use the maker list below.",
              );
          })
          .addTo(instance);
        layer.current = L.layerGroup().addTo(instance);
        instance.on("click", (event) =>
          handlers.current.onPick?.(
            approximate(
              event.latlng.lat,
              ((((event.latlng.lng + 180) % 360) + 360) % 360) - 180,
            ),
          ),
        );
        observer = new ResizeObserver(() => instance.invalidateSize());
        observer.observe(host.current);
        setReady(true);
      })
      .catch(() => {
        if (active)
          setError("The map couldn’t load. You can still browse makers below.");
      });
    return () => {
      active = false;
      observer?.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!ready || !map.current) return;
    const L = leaflet.current;
    layer.current.clearLayers();
    const bounds = [];
    if (point) {
      const position = coords(point);
      bounds.push(position);
      L.circle(position, {
        radius: 800,
        color: "#9a7745",
        weight: 1,
        fillOpacity: 0.09,
      }).addTo(layer.current);
      L.circleMarker(position, {
        radius: 7,
        color: "#fffaf0",
        weight: 3,
        fillColor: "#9a7745",
        fillOpacity: 1,
      })
        .bindTooltip(editor ? "Your public workroom area" : "Your search area")
        .addTo(layer.current);
    }
    makers
      .filter((maker) => maker.public_location)
      .forEach((maker) => {
        const position = coords(maker.public_location);
        bounds.push(position);
        const popup = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = maker.name;
        const description = document.createElement("p");
        description.textContent = `${maker.city} · ${maker.distance_km != null ? `about ${maker.distance_km} km away` : "approximate location"}`;
        popup.append(title, description);
        if (onChoose) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = "Choose this maker";
          button.addEventListener("click", () =>
            handlers.current.onChoose?.(maker),
          );
          popup.append(button);
        }
        L.marker(position, {
          title: maker.name,
          icon: L.divIcon({
            className: "workroom-pin",
            html: '<span aria-hidden="true">金</span>',
            iconSize: [32, 38],
            iconAnchor: [16, 38],
          }),
        })
          .bindPopup(popup)
          .addTo(layer.current);
      });
    if (bounds.length > 1)
      map.current.fitBounds(bounds, {
        padding: [35, 35],
        maxZoom: 13,
        animate: false,
      });
    else if (bounds.length === 1)
      map.current.setView(bounds[0], 12, { animate: false });
    else map.current.setView(INDIA, 4, { animate: false });
  }, [ready, point, makers, editor]);
  return (
    <>
      <div
        ref={host}
        className="workroom-map"
        role="region"
        aria-label={
          editor
            ? "Choose your public workroom area on OpenStreetMap"
            : "OpenStreetMap of nearby makers"
        }
      />
      {error && (
        <p className="map-feedback" role="status">
          {error}
        </p>
      )}
    </>
  );
}

function AreaControls({ onPick }) {
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const valid =
    latitude !== "" &&
    longitude !== "" &&
    Number.isFinite(Number(latitude)) &&
    Number.isFinite(Number(longitude)) &&
    Math.abs(Number(latitude)) <= 90 &&
    Math.abs(Number(longitude)) <= 180;
  return (
    <details className="manual-area">
      <summary>Choose an area without location access</summary>
      <p>Tap the map, or enter the coordinates of a town or neighbourhood.</p>
      <div>
        <label>
          Latitude
          <input
            type="number"
            min="-90"
            max="90"
            step="any"
            value={latitude}
            onChange={(e) => setLatitude(e.target.value)}
          />
        </label>
        <label>
          Longitude
          <input
            type="number"
            min="-180"
            max="180"
            step="any"
            value={longitude}
            onChange={(e) => setLongitude(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="secondary"
          disabled={!valid}
          onClick={() =>
            onPick(approximate(Number(latitude), Number(longitude)))
          }
        >
          Use this area
        </button>
      </div>
    </details>
  );
}

export function MakerLocationEditor({ value, onChange }) {
  const { locate, locating, error } = useLocation(onChange);
  return (
    <section className="maker-location-editor">
      <span className="app-kicker">YOUR PUBLIC WORKROOM AREA · OPTIONAL</span>
      <p>
        Help nearby customers find you. Choose a neighbourhood, rather than your
        front door. The pin is rounded to roughly a kilometre; your collection
        address stays private.
      </p>
      <button
        type="button"
        className="secondary"
        onClick={locate}
        disabled={locating}
      >
        <LocateFixed size={15} />
        {locating ? "Finding your location…" : "Use my location"}
      </button>
      {error && (
        <p className="map-feedback" role="status">
          {error}
        </p>
      )}
      <MapCanvas point={value} onPick={onChange} editor />
      <AreaControls onPick={onChange} />
      {value && (
        <p className="map-feedback">
          Selected area: {value.latitude.toFixed(2)},{" "}
          {value.longitude.toFixed(2)}{" "}
          <button
            type="button"
            className="text-link"
            onClick={() => onChange(null)}
          >
            Remove pin
          </button>
        </p>
      )}
      <small>
        Saving this location consents to showing the approximate pin publicly
        once your workroom is approved.
      </small>
    </section>
  );
}

export default function NearbyMakers({
  category: fixedCategory,
  onChoose,
  selectedId,
}) {
  const [point, setPoint] = useState(null);
  const [radius, setRadius] = useState(50);
  const [category, setCategory] = useState("");
  const [makers, setMakers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const { locate, locating, error: locationError } = useLocation(setPoint);
  const selectedCategory = fixedCategory || category;
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setMakers([]);
    const query = new URLSearchParams();
    if (selectedCategory) query.set("category", selectedCategory);
    if (point) {
      query.set("latitude", point.latitude);
      query.set("longitude", point.longitude);
      query.set("radius_km", radius);
    }
    api(`/network/makers?${query}`)
      .then((result) => {
        if (active) setMakers(result);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [point, radius, selectedCategory, retry]);
  return (
    <section className="nearby-makers">
      <div className="nearby-heading">
        <div>
          <span className="app-kicker">CRAFT, CLOSER TO HOME</span>
          <h2>Find a maker near you.</h2>
          <p>A skilled pair of hands might be closer than you think.</p>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={locate}
          disabled={locating}
        >
          <LocateFixed size={16} />
          {locating
            ? "Finding your location…"
            : point
              ? "Refresh my location"
              : "Use my location"}
        </button>
      </div>
      <p className="location-privacy">
        Your browser will ask permission. We use an approximate area for this
        search only, without saving your location to your account.
      </p>
      {locationError && (
        <p className="map-feedback" role="status">
          {locationError}
        </p>
      )}
      <div className="nearby-filters">
        {!fixedCategory && (
          <label>
            Craft
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All crafts</option>
              <option value="textile">Clothing & textiles</option>
              <option value="ceramic">Decorative ceramics</option>
            </select>
          </label>
        )}
        <label>
          Search within
          <select
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          >
            {[25, 50, 100, 200].map((km) => (
              <option key={km} value={km}>
                {km} km
              </option>
            ))}
          </select>
        </label>
        {point && (
          <button
            type="button"
            className="text-link"
            onClick={() => setPoint(null)}
          >
            Browse all makers
          </button>
        )}
      </div>
      <MapCanvas
        point={point}
        makers={makers}
        onPick={setPoint}
        onChoose={onChoose}
      />
      <AreaControls onPick={setPoint} />
      <p className="map-caption">
        <MapPin size={13} />
        Workroom pins are approximate. Distances are straight-line estimates,
        not delivery routes.
      </p>
      <div aria-live="polite" aria-busy={loading}>
        {error ? (
          <p className="map-feedback" role="alert">
            {error}{" "}
            <button
              type="button"
              className="text-link"
              onClick={() => setRetry((value) => value + 1)}
            >
              Try again
            </button>
          </p>
        ) : loading ? (
          <p className="map-feedback">Looking for available makers…</p>
        ) : (
          <>
            <p className="map-feedback">
              {point
                ? `${makers.length}${makers.length === 50 ? "+" : ""} available makers within ${radius} km`
                : "Approved workrooms accepting repairs"}
            </p>
            {!makers.length && (
              <div className="nearby-empty">
                <h3>
                  {point
                    ? "No nearby workrooms just yet."
                    : "The network is taking shape."}
                </h3>
                <p>
                  {point
                    ? "Try a wider radius, or browse all makers. You can also ask Kintsugi to match your repair and coordinate shipping."
                    : "Approved makers will appear here when they’re ready for work. You can still request a repair and let Kintsugi arrange a match."}
                </p>
              </div>
            )}
            <div className="nearby-list">
              {makers.map((maker) => (
                <article
                  key={maker.id}
                  className={selectedId === maker.id ? "chosen" : ""}
                >
                  <span>{communities[maker.community]}</span>
                  <h3>{maker.name}</h3>
                  <p>
                    {maker.city} · {maker.categories.join(" & ")}
                    {maker.distance_km != null
                      ? ` · about ${maker.distance_km} km away`
                      : !maker.public_location
                        ? " · Map location not added"
                        : ""}
                  </p>
                  <p>{maker.about}</p>
                  {onChoose && (
                    <button
                      type="button"
                      className="text-link"
                      onClick={() => onChoose(maker)}
                    >
                      {selectedId === maker.id
                        ? "Selected maker"
                        : "Choose this maker"}
                      <ArrowUpRight size={14} />
                    </button>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
