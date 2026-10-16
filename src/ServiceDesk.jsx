import React, { useEffect, useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  ChevronLeft,
  Check,
  Package,
  Truck,
  Scissors,
} from "lucide-react";
import { api, asset } from "./api";
import "./services.css";
import NearbyMakers, { MakerLocationEditor } from "./MakerMap";
const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format((value || 0) / 100);
const minor = (value) => (value ? Math.round(Number(value) * 100) : null);
const statusNames = {
  awaiting_match: "Finding the right maker",
  awaiting_quote: "With the maker for a quote",
  repair_priced: "Arranging shipping costs",
  quoted: "Your quote is ready",
  accepted: "Quote accepted · arranging pickup",
  pickup_scheduled: "Pickup scheduled",
  on_way_to_maker: "On the way to your maker",
  with_maker: "Safely with the maker",
  repairing: "Repair in progress",
  ready_for_return: "Repair finished",
  return_scheduled: "Return pickup scheduled",
  on_way_home: "On the way home",
  delivered: "Home again",
  cancelled: "Cancelled",
};
const communityNames = {
  independent: "Independent business",
  women_led: "Women-led business",
  community_enterprise: "Community enterprise",
};
function AddressFields({ name = "" }) {
  return (
    <div className="address-fields">
      <label>
        Recipient name
        <input
          name="address_name"
          defaultValue={name}
          required
          minLength={2}
          maxLength={100}
          autoComplete="name"
        />
      </label>
      <label>
        Phone
        <input
          name="address_phone"
          required
          minLength={8}
          maxLength={20}
          type="tel"
          autoComplete="tel"
        />
      </label>
      <label className="full">
        Street address
        <input
          name="address_line1"
          required
          minLength={5}
          maxLength={200}
          autoComplete="street-address"
        />
      </label>
      <label>
        City
        <input
          name="address_city"
          required
          minLength={2}
          maxLength={80}
          autoComplete="address-level2"
        />
      </label>
      <label>
        PIN code
        <input
          name="address_postal_code"
          required
          pattern="[0-9]{6}"
          inputMode="numeric"
          autoComplete="postal-code"
        />
      </label>
      <small className="full">
        Domestic India shipping · Address shared with Kintsugi operations for
        collection and return.
      </small>
    </div>
  );
}
function address(data) {
  return {
    name: data.get("address_name"),
    phone: data.get("address_phone"),
    line1: data.get("address_line1"),
    city: data.get("address_city"),
    postal_code: data.get("address_postal_code"),
    country: "IN",
  };
}
function Quote({ quote, ready }) {
  if (!quote) return null;
  return (
    <section className="service-quote">
      <span className="app-kicker">THE PRICE, IN FULL · INR</span>
      <dl>
        <div>
          <dt>Maker’s labour</dt>
          <dd>{money(quote.labour_minor)}</dd>
        </div>
        <div>
          <dt>Materials</dt>
          <dd>{money(quote.materials_minor)}</dd>
        </div>
        {ready ? (
          <>
            <div>
              <dt>Shipping to the maker</dt>
              <dd>{money(quote.outbound_minor)}</dd>
            </div>
            <div>
              <dt>Shipping back to you</dt>
              <dd>{money(quote.return_minor)}</dd>
            </div>
            <div>
              <dt>Kintsugi service fee</dt>
              <dd>{money(quote.fee_minor)}</dd>
            </div>
            <div className="quote-total">
              <dt>Total</dt>
              <dd>{money(quote.total_minor)}</dd>
            </div>
          </>
        ) : (
          <div>
            <dt>Shipping and service fee</dt>
            <dd>Being arranged</dd>
          </div>
        )}
      </dl>
      <p className="maker-pay">
        {money(quote.maker_earns_minor)} goes to the maker for labour and
        materials. The platform fee is separate.
      </p>
      {ready && quote.saving_minor !== null && (
        <p className="quote-comparison">
          {quote.saving_minor > 0
            ? `${money(quote.saving_minor)} less than your replacement estimate.`
            : quote.saving_minor < 0
              ? `${money(-quote.saving_minor)} above your replacement estimate. You can decline before accepting.`
              : "The same as your replacement estimate."}
        </p>
      )}
      <p>{quote.notes}</p>
      <small>
        Estimated craft time: {quote.days} days after the piece arrives, plus
        transit.
      </small>
    </section>
  );
}
export default function ServiceDesk({
  account,
  project,
  projects,
  onStartUpload,
}) {
  const [scope, setScope] = useState("customer"),
    [mode, setMode] = useState(project ? "request" : "list"),
    [selected, setSelected] = useState(null),
    [list, setList] = useState([]),
    [makers, setMakers] = useState([]),
    [profile, setProfile] = useState(null),
    [earnings, setEarnings] = useState([]),
    [applications, setApplications] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [pieceId, setPieceId] = useState(project?.id || projects[0]?.id || "");
  const [chosenMaker, setChosenMaker] = useState(null);
  const [publicLocation, setPublicLocation] = useState(null);
  const allProjects =
    project && !projects.some((p) => p.id === project.id)
      ? [project, ...projects]
      : projects;
  const piece = allProjects.find((p) => p.id === pieceId);
  useEffect(() => {
    if (
      chosenMaker &&
      piece &&
      !chosenMaker.categories.includes(piece.category)
    )
      setChosenMaker(null);
  }, [piece?.id, chosenMaker]);
  async function refresh() {
    const [requests, directory, me, paid] = await Promise.all([
      api("/network/requests?scope=" + scope),
      api("/network/makers"),
      api("/network/profile"),
      api("/network/earnings"),
    ]);
    setList(requests);
    setMakers(directory);
    setProfile(me);
    setPublicLocation(me?.public_location || null);
    setEarnings(paid);
    if (account.role === "operator")
      setApplications(await api("/network/applications"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [scope]);
  useEffect(() => {
    if (!selected || mode !== "detail") return;
    let active = true;
    let timer;
    const poll = async () => {
      try {
        const fresh = await api("/network/requests/" + selected.id);
        if (active) setSelected(fresh);
      } catch {}
      if (active) timer = setTimeout(poll, 6000);
    };
    timer = setTimeout(poll, 6000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [selected?.id, mode]);
  async function run(fn, after) {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      await refresh();
      if (after) after(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const action = (suffix, body) =>
    run(
      () =>
        api(`/network/requests/${selected.id}/${suffix}`, {
          method: "POST",
          body,
        }),
      (result) => {
        if (result.id) setSelected(result);
        else api("/network/requests/" + selected.id).then(setSelected);
      },
    );
  const back = () => {
    setMode("list");
    setSelected(null);
    setError("");
    refresh().catch((e) => setError(e.message));
  };
  return (
    <div className="service-desk">
      <div className="network-heading">
        <div>
          <span className="app-kicker">THE KINTSUGI REPAIR NETWORK</span>
          <h1>
            Someone’s craft.
            <br />
            <em>Your piece, kept.</em>
          </h1>
        </div>
        <p>
          A repair you love should not depend on skills you haven’t learned.
          Commission an independent maker, with collection and return
          coordinated through Kintsugi.
        </p>
      </div>
      <div className="network-tabs">
        <button
          className={scope === "customer" ? "active" : ""}
          onClick={() => {
            setScope("customer");
            setMode("list");
          }}
        >
          My repairs
        </button>
        <button
          className={scope === "maker" ? "active" : ""}
          onClick={() => {
            setScope("maker");
            setMode("list");
          }}
        >
          Maker workroom
        </button>
        {account.role === "operator" && (
          <button
            className={scope === "operator" ? "active" : ""}
            onClick={() => {
              setScope("operator");
              setMode("list");
            }}
          >
            Operations
          </button>
        )}
      </div>
      {error && (
        <div className="app-error" role="alert">
          {error}
        </div>
      )}
      {mode !== "list" && (
        <button className="text-link service-back" onClick={back}>
          <ChevronLeft size={14} />
          Back to repair services
        </button>
      )}
      {mode === "request" ? (
        <div className="service-request-layout">
          <div>
            <h2>Tell us what you have in mind.</h2>
            <p>
              We’ll ask a maker to assess the work before you commit. Requesting
              a quote costs nothing.
            </p>
            {allProjects.length === 0 ? (
              <>
                <p>Add a photo of your piece first.</p>
                <button className="primary" onClick={onStartUpload}>
                  Add my piece <ArrowRight size={16} />
                </button>
              </>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  run(
                    () =>
                      api("/network/requests", {
                        method: "POST",
                        body: {
                          project_id: pieceId,
                          maker_id: chosenMaker?.id || null,
                          brief: data.get("brief"),
                          replacement_minor: minor(data.get("replacement")),
                          budget_minor: minor(data.get("budget")),
                          consent_to_share: true,
                        },
                      }),
                    (result) => {
                      setSelected(result);
                      setMode("detail");
                    },
                  );
                }}
              >
                <label>
                  Your piece
                  <select
                    value={pieceId}
                    onChange={(e) => {
                      setPieceId(e.target.value);
                      setChosenMaker(null);
                    }}
                  >
                    {allProjects.map((p) => (
                      <option value={p.id} key={p.id}>
                        {p.title} ·{" "}
                        {p.category === "ceramic" ? "ceramic" : "textile"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  The repair you’re imagining
                  <textarea
                    name="brief"
                    key={pieceId}
                    defaultValue={
                      piece?.tutorial_steps?.length
                        ? `I started the guided repair and completed ${piece.tutorial_steps.length} of 6 steps. I would like a maker to help finish it.`
                        : ""
                    }
                    required
                    minLength={10}
                    maxLength={1000}
                    placeholder="The gold branching repair is beautiful, but I need someone to sew it. I’d like to keep the original fabric…"
                  />
                </label>
                <div className="two-fields">
                  <label>
                    Replacement estimate (₹)
                    <input
                      name="replacement"
                      type="number"
                      min="1"
                      max="1000000"
                      step=".01"
                      placeholder="Optional"
                    />
                  </label>
                  <label>
                    Your preferred budget (₹)
                    <input
                      name="budget"
                      type="number"
                      min="1"
                      max="1000000"
                      step=".01"
                      placeholder="Optional"
                    />
                  </label>
                </div>
                <label>
                  Your maker
                  <select
                    name="maker_id"
                    value={chosenMaker?.id || ""}
                    onChange={(e) =>
                      setChosenMaker(
                        makers.find((m) => m.id === e.target.value) ||
                          (chosenMaker?.id === e.target.value
                            ? chosenMaker
                            : null),
                      )
                    }
                  >
                    <option value="">Let Kintsugi find the right maker</option>
                    {Array.from(
                      new Map(
                        [...makers, ...(chosenMaker ? [chosenMaker] : [])].map(
                          (m) => [m.id, m],
                        ),
                      ).values(),
                    )
                      .filter((m) => m.categories.includes(piece?.category))
                      .map((m) => (
                        <option value={m.id} key={m.id}>
                          {m.name} · {m.city}
                        </option>
                      ))}
                  </select>
                </label>
                <NearbyMakers
                  category={piece?.category}
                  selectedId={chosenMaker?.id}
                  onChoose={setChosenMaker}
                />
                <label className="confirm-check">
                  <input type="checkbox" required />I agree to share this
                  piece’s photo, chosen repair plan and brief with the assigned
                  maker so they can assess the work.
                </label>
                <button className="primary" disabled={busy}>
                  Request a quote <ArrowUpRight size={16} />
                </button>
              </form>
            )}
          </div>
          <aside className="service-promise">
            <Package size={24} />
            <h3>Care in both directions.</h3>
            <p>
              A maker’s quote, plus materials, both shipping legs, and a
              separate service fee. You see the total before you accept.
            </p>
            <p>
              We compare it with your replacement estimate when you provide one.
              The price depends on the work; a lower price is never guaranteed.
            </p>
            <small>
              Quotes and courier bookings are coordinated by an operator. This
              app does not currently collect payments or purchase shipping
              labels.
            </small>
          </aside>
        </div>
      ) : mode === "apply" ? (
        <div className="maker-application">
          <span className="app-kicker">INDEPENDENT WORK. YOUR PRICE.</span>
          <h2>
            Make your craft
            <br />
            part of someone’s story.
          </h2>
          <p>
            Set your labour and materials price. Choose the jobs you take.
            Kintsugi coordinates the customer and shipping, while you focus on
            the work.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              run(
                () =>
                  api("/network/profile", {
                    method: "POST",
                    body: {
                      name: data.get("business_name"),
                      about: data.get("about"),
                      city: data.get("city"),
                      categories: data.getAll("categories"),
                      community: data.get("community"),
                      address: address(data),
                      consent_to_list: true,
                      public_location: publicLocation,
                    },
                  }),
                () => setMode("list"),
              );
            }}
          >
            <label>
              Business or workroom name
              <input
                name="business_name"
                required
                minLength={2}
                maxLength={100}
              />
            </label>
            <label>
              Your craft
              <textarea
                name="about"
                required
                minLength={30}
                maxLength={1000}
                placeholder="Tell us about your skills, experience and the repairs you take on."
              />
            </label>
            <label>
              Public city
              <input name="city" required minLength={2} maxLength={80} />
            </label>
            <fieldset className="category-checks">
              <legend>What do you repair?</legend>
              <label>
                <input type="checkbox" name="categories" value="textile" />
                Clothing and textiles
              </label>
              <label>
                <input type="checkbox" name="categories" value="ceramic" />
                Decorative ceramics
              </label>
            </fieldset>
            <label>
              How would you describe your workroom?
              <select name="community">
                <option value="independent">Independent business</option>
                <option value="women_led">Women-led business</option>
                <option value="community_enterprise">
                  Community enterprise
                </option>
              </select>
            </label>
            <small>
              This is optional self-description, not a demographic assessment or
              eligibility claim.
            </small>
            <MakerLocationEditor
              value={publicLocation}
              onChange={setPublicLocation}
            />
            <h3>Private collection address</h3>
            <AddressFields name={account.name} />
            <label className="confirm-check">
              <input type="checkbox" required />I agree to list my workroom
              name, craft description, city and business description after
              operator approval. My street address and phone stay private to
              operations.
            </label>
            <button className="primary" disabled={busy}>
              Submit my application <ArrowRight size={16} />
            </button>
          </form>
        </div>
      ) : mode === "detail" && selected ? (
        <div className="service-detail">
          <div className="service-detail-main">
            <div className="service-status">
              <span className="app-kicker">{statusNames[selected.status]}</span>
              <h2>{selected.title}</h2>
              <p>{selected.brief}</p>
            </div>
            <img
              className="service-photo"
              src={asset(`/network/requests/${selected.id}/image`)}
              alt={selected.title}
            />
            {selected.design?.has_preview && (
              <section className="shared-repair-preview">
                <span className="app-kicker">
                  THE SHARED REPAIR CONCEPT · AI VISUALISATION
                </span>
                <h3>{selected.design.name}</h3>
                <img
                  className="service-photo"
                  src={asset(`/network/requests/${selected.id}/preview.png`)}
                  alt={`Imagined repair: ${selected.design.name}`}
                />
              </section>
            )}
            {selected.category === "ceramic" && (
              <p className="app-note">
                Ceramic repair requires an assessment of safe use, fragility and
                packaging. A restored decorative piece is not automatically
                food-safe or suitable for heat or structural use.
              </p>
            )}
            <div className="shared-design">
              {selected.design && (
                <>
                  <span className="app-kicker">SHARED WITH YOUR MAKER</span>
                  <h3>{selected.design.name}</h3>
                  {selected.design.tutorial_completed_steps?.length > 0 && (
                    <p>
                      {selected.design.tutorial_completed_steps.length} of 6 DIY
                      steps marked complete by the customer.
                    </p>
                  )}
                  {selected.design.has_pattern && (
                    <a
                      className="text-link"
                      href={asset(
                        `/network/requests/${selected.id}/pattern.pdf`,
                      )}
                      download
                    >
                      Download shared repair guide <ArrowUpRight size={14} />
                    </a>
                  )}
                </>
              )}
            </div>
            <div className="service-timeline">
              <h3>The journey</h3>
              {selected.events.map((item, i) => (
                <div key={i}>
                  <span />
                  <p>
                    {item.message}
                    <small>
                      {new Date(item.created_at * 1000).toLocaleString()}
                    </small>
                  </p>
                </div>
              ))}
            </div>
            {selected.shipments.length > 0 && (
              <div className="shipment-list">
                <h3>Collection & return</h3>
                {selected.shipments.map((s) => (
                  <div key={s.id}>
                    <Truck size={18} />
                    <div>
                      <strong>
                        {s.leg === "outbound" ? "To the maker" : "Back to you"}
                      </strong>
                      <span>
                        {s.status.replace("_", " ")}
                        {s.courier ? " · " + s.courier : ""}
                      </span>
                      {s.tracking && <small>{s.tracking}</small>}
                      {s.tracking_url && (
                        <a
                          href={s.tracking_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Carrier tracking ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <aside className="service-detail-aside">
            {selected.maker ? (
              <div className="assigned-maker">
                <span className="app-kicker">THE HANDS BEHIND THE WORK</span>
                <h3>{selected.maker.name}</h3>
                <p>
                  {selected.maker.city} ·{" "}
                  {communityNames[selected.maker.community]}
                </p>
                <p>{selected.maker.about}</p>
              </div>
            ) : (
              <div className="assigned-maker">
                <h3>Finding a skilled hand.</h3>
                <p>
                  Your request is saved for the Kintsugi operator. No maker or
                  pickup is confirmed yet.
                </p>
              </div>
            )}
            <Quote
              quote={selected.quote}
              ready={
                !["awaiting_quote", "repair_priced"].includes(selected.status)
              }
            />
            {scope === "customer" && selected.status === "quoted" && (
              <form
                className="service-action-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  action("accept", {
                    version: selected.quote.version,
                    address: address(data),
                    packaging_acknowledged: true,
                  });
                }}
              >
                <h3>Where should we collect it?</h3>
                <AddressFields name={account.name} />
                <label className="confirm-check">
                  <input type="checkbox" required />I accept this itemised quote
                  and will package the item for safe transit. For fragile
                  objects, I’ll wait for packing guidance before pickup.
                </label>
                <button className="primary" disabled={busy}>
                  Accept {money(selected.quote.total_minor)} quote{" "}
                  <Check size={15} />
                </button>
                <p className="app-note">
                  Accepting saves the quote and starts coordination. No online
                  payment is taken. An operator will arrange payment and confirm
                  a carrier booking.
                </p>
              </form>
            )}
            {scope === "customer" &&
              [
                "awaiting_match",
                "awaiting_quote",
                "repair_priced",
                "quoted",
              ].includes(selected.status) && (
                <button
                  className="text-link cancel-service"
                  disabled={busy}
                  onClick={() => action("cancel")}
                >
                  Cancel this request
                </button>
              )}
            {scope === "maker" &&
              ["awaiting_quote", "repair_priced"].includes(selected.status) && (
                <form
                  className="service-action-form"
                  key={selected.quote?.version || 0}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    action("quote", {
                      labour_minor: minor(data.get("labour")),
                      materials_minor: minor(data.get("materials")) || 0,
                      days: Number(data.get("days")),
                      notes: data.get("notes"),
                    });
                  }}
                >
                  <h3>Your craft. Your quote.</h3>
                  <p>
                    You receive your full labour and materials amount. Shipping
                    and the platform fee are quoted separately to the customer.
                  </p>
                  <div className="two-fields">
                    <label>
                      Labour (₹)
                      <input
                        type="number"
                        name="labour"
                        min="1"
                        step=".01"
                        required
                        defaultValue={
                          selected.quote
                            ? selected.quote.labour_minor / 100
                            : ""
                        }
                      />
                    </label>
                    <label>
                      Materials (₹)
                      <input
                        type="number"
                        name="materials"
                        min="0"
                        step=".01"
                        required
                        defaultValue={
                          selected.quote
                            ? selected.quote.materials_minor / 100
                            : 0
                        }
                      />
                    </label>
                  </div>
                  <label>
                    Craft time in days
                    <input
                      type="number"
                      name="days"
                      required
                      min="1"
                      max="90"
                      defaultValue={selected.quote?.days || 7}
                    />
                  </label>
                  <label>
                    Scope and finish
                    <textarea
                      name="notes"
                      required
                      minLength={10}
                      maxLength={1000}
                      defaultValue={selected.quote?.notes || ""}
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    Submit repair price <ArrowRight size={15} />
                  </button>
                  {selected.status === "awaiting_quote" && (
                    <button
                      className="text-link cancel-service"
                      type="button"
                      disabled={busy}
                      onClick={() => action("progress", { status: "declined" })}
                    >
                      Decline this job
                    </button>
                  )}
                </form>
              )}
            {scope === "maker" && selected.status === "with_maker" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() => action("progress", { status: "repairing" })}
              >
                Start the repair <Scissors size={15} />
              </button>
            )}
            {scope === "maker" && selected.status === "repairing" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  action("progress", { status: "ready_for_return" })
                }
              >
                Repair finished · ready to return <Check size={15} />
              </button>
            )}
            {scope === "operator" && (
              <div className="operator-actions">
                {selected.status === "awaiting_match" && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      action("assign", {
                        maker_id: new FormData(e.currentTarget).get("maker"),
                      });
                    }}
                  >
                    <h3>Match this repair</h3>
                    <label>
                      Approved maker
                      <select name="maker" required>
                        <option value="">Choose a maker</option>
                        {makers
                          .filter((m) =>
                            m.categories.includes(selected.category),
                          )
                          .map((m) => (
                            <option value={m.id} key={m.id}>
                              {m.name} · {m.city}
                            </option>
                          ))}
                      </select>
                    </label>
                    <button className="secondary" disabled={busy}>
                      Assign maker
                    </button>
                  </form>
                )}
                {["repair_priced", "quoted"].includes(selected.status) && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const data = new FormData(e.currentTarget);
                      action("shipping-price", {
                        version: selected.quote.version,
                        outbound_minor: minor(data.get("outbound")) || 0,
                        return_minor: minor(data.get("return")) || 0,
                      });
                    }}
                  >
                    <h3>Confirm the shipping estimate</h3>
                    <label>
                      Outbound shipping (₹)
                      <input
                        type="number"
                        name="outbound"
                        min="0"
                        step=".01"
                        required
                      />
                    </label>
                    <label>
                      Return shipping (₹)
                      <input
                        type="number"
                        name="return"
                        min="0"
                        step=".01"
                        required
                      />
                    </label>
                    <p className="app-note">
                      Enter actual carrier estimates. The configured platform
                      fee is added separately by the server. The customer must
                      accept the complete quote.
                    </p>
                    <button className="secondary" disabled={busy}>
                      Publish itemised quote
                    </button>
                  </form>
                )}
                {selected.status === "accepted" &&
                  selected.payment_status !== "confirmed" && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        action("payment", {
                          reference: new FormData(e.currentTarget).get(
                            "reference",
                          ),
                        });
                      }}
                    >
                      <h3>Reconcile received payment</h3>
                      <label>
                        External payment reference
                        <input
                          name="reference"
                          required
                          minLength={5}
                          maxLength={120}
                        />
                      </label>
                      <button className="secondary" disabled={busy}>
                        Record payment received
                      </button>
                    </form>
                  )}
                {selected.return_address && (
                  <details>
                    <summary>Private logistics addresses</summary>
                    <p>
                      <strong>Customer</strong>
                      <br />
                      {Object.values(selected.return_address).join(" · ")}
                    </p>
                    <p>
                      <strong>Maker</strong>
                      <br />
                      {selected.maker_address
                        ? Object.values(selected.maker_address).join(" · ")
                        : "Not assigned"}
                    </p>
                  </details>
                )}
                {[
                  "accepted",
                  "pickup_scheduled",
                  "on_way_to_maker",
                  "ready_for_return",
                  "return_scheduled",
                  "on_way_home",
                ].includes(selected.status) &&
                  selected.payment_status === "confirmed" && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        const leg = [
                          "accepted",
                          "pickup_scheduled",
                          "on_way_to_maker",
                        ].includes(selected.status)
                          ? "outbound"
                          : "return";
                        const status = {
                          accepted: "scheduled",
                          pickup_scheduled: "in_transit",
                          on_way_to_maker: "delivered",
                          ready_for_return: "scheduled",
                          return_scheduled: "in_transit",
                          on_way_home: "delivered",
                        }[selected.status];
                        action("shipments/" + leg, {
                          status,
                          courier: data.get("courier"),
                          tracking: data.get("tracking"),
                          tracking_url: data.get("tracking_url") || null,
                          pickup_at: data.get("pickup_at") || null,
                        });
                      }}
                    >
                      <h3>Record the next carrier event</h3>
                      <label>
                        Carrier
                        <input
                          name="courier"
                          required
                          minLength={2}
                          maxLength={80}
                        />
                      </label>
                      <label>
                        Tracking / booking reference
                        <input
                          name="tracking"
                          required
                          minLength={3}
                          maxLength={120}
                        />
                      </label>
                      <label>
                        HTTPS tracking link
                        <input
                          name="tracking_url"
                          type="url"
                          placeholder="https://…"
                        />
                      </label>
                      <label>
                        Pickup date and time
                        <input
                          name="pickup_at"
                          type="datetime-local"
                          required={["accepted", "ready_for_return"].includes(
                            selected.status,
                          )}
                        />
                      </label>
                      <p className="app-note">
                        This records a booking or carrier update already made
                        outside the app. It does not buy a label or call a
                        carrier.
                      </p>
                      <button className="secondary" disabled={busy}>
                        Record carrier event
                      </button>
                    </form>
                  )}
                {selected.status === "delivered" && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      action("payout", {
                        reference: new FormData(e.currentTarget).get(
                          "reference",
                        ),
                      });
                    }}
                  >
                    <h3>Reconcile the maker payout</h3>
                    <label>
                      External transfer reference
                      <input
                        name="reference"
                        required
                        minLength={5}
                        maxLength={120}
                      />
                    </label>
                    <button className="secondary" disabled={busy}>
                      Record payout completed
                    </button>
                    <p className="app-note">
                      Only record this after an actual transfer. This action
                      does not move money.
                    </p>
                  </form>
                )}
              </div>
            )}
          </aside>
        </div>
      ) : (
        <>
          {scope === "customer" ? (
            <>
              <div className="network-principle">
                <div>
                  <h2>
                    Repair can create
                    <br />a livelihood.
                  </h2>
                  <p>
                    Women-led workrooms, small businesses and independent
                    craftspeople bring skills you may not have. This is paid
                    work at their quoted price. Kintsugi handles the
                    coordination around it.
                  </p>
                </div>
                <button className="primary" onClick={() => setMode("request")}>
                  Request a repair <ArrowUpRight size={16} />
                </button>
              </div>
              <NearbyMakers
                onChoose={(maker) => {
                  setChosenMaker(maker);
                  const matching = allProjects.find((p) =>
                    maker.categories.includes(p.category),
                  );
                  if (matching) setPieceId(matching.id);
                  setMode("request");
                }}
              />
            </>
          ) : scope === "maker" ? (
            <>
              <div className="network-principle">
                <div>
                  <h2>
                    Build a workroom
                    <br />
                    on your own terms.
                  </h2>
                  <p>
                    Price your skill, choose the work, and see what you’ll earn.
                    Your labour and materials amount belongs to you; the
                    customer’s platform fee is separate.
                  </p>
                </div>
                {!profile ? (
                  <button className="primary" onClick={() => setMode("apply")}>
                    Apply as a maker <ArrowUpRight size={16} />
                  </button>
                ) : (
                  <div>
                    <span className="status">
                      {profile.status === "approved"
                        ? "Approved workroom"
                        : profile.status === "pending"
                          ? "Application awaiting review"
                          : "Application not approved"}
                    </span>
                    {profile.status === "approved" && (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(() =>
                            api("/network/profile/availability", {
                              method: "POST",
                              body: { accepting_work: !profile.accepting_work },
                            }),
                          )
                        }
                      >
                        {profile.accepting_work
                          ? "Pause new work"
                          : "Accept new work"}
                      </button>
                    )}
                  </div>
                )}
              </div>
              {profile && (
                <details className="maker-location-settings">
                  <summary>Manage my public map location</summary>
                  <MakerLocationEditor
                    value={publicLocation}
                    onChange={setPublicLocation}
                  />
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        api("/network/profile/location", {
                          method: "PUT",
                          body: { public_location: publicLocation },
                        }),
                      )
                    }
                  >
                    Save public map location
                  </button>
                </details>
              )}
              {earnings.length > 0 && (
                <section className="maker-earnings">
                  <h3>Your work, accounted for.</h3>
                  {earnings.map((e) => (
                    <div key={e.id}>
                      <span>Repair {e.service_id.slice(0, 8)}</span>
                      <strong>{money(e.amount_minor)}</strong>
                      <span>{e.status.replaceAll("_", " ")}</span>
                    </div>
                  ))}
                  <p className="app-note">
                    Amounts await delivery before becoming payable. “Paid” means
                    an operator has recorded an external transfer reference.
                  </p>
                </section>
              )}
            </>
          ) : (
            <>
              {applications.length > 0 && (
                <section className="maker-applications">
                  <h2>Maker applications</h2>
                  {applications.map((m) => (
                    <article key={m.id}>
                      <div>
                        <h3>
                          {m.name} · {m.city}
                        </h3>
                        <p>{m.about}</p>
                        <small>
                          {m.categories.join(", ")} ·{" "}
                          {communityNames[m.community]}
                        </small>
                      </div>
                      <div>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() =>
                            run(() =>
                              api(`/network/makers/${m.id}/review`, {
                                method: "POST",
                                body: { decision: "approved" },
                              }),
                            )
                          }
                        >
                          Approve
                        </button>
                        <button
                          className="text-link"
                          disabled={busy}
                          onClick={() =>
                            run(() =>
                              api(`/network/makers/${m.id}/review`, {
                                method: "POST",
                                body: { decision: "rejected" },
                              }),
                            )
                          }
                        >
                          Decline
                        </button>
                      </div>
                    </article>
                  ))}
                </section>
              )}
            </>
          )}
          <section className="service-requests">
            <div className="request-list-heading">
              <h2>
                {scope === "customer"
                  ? "Your repair requests"
                  : scope === "maker"
                    ? "Your assigned work"
                    : "Repair operations"}
              </h2>
              <button
                className="text-link"
                onClick={() => refresh().catch((e) => setError(e.message))}
              >
                Refresh
              </button>
            </div>
            {list.length === 0 ? (
              <p className="service-empty">
                {scope === "customer"
                  ? "No requests yet. Start with a piece you want to keep."
                  : scope === "maker"
                    ? "Assigned jobs will appear here after your workroom is approved and matched."
                    : "No repair requests are waiting."}
              </p>
            ) : (
              list.map((item) => (
                <button
                  className="request-row"
                  key={item.id}
                  onClick={() => {
                    setSelected(item);
                    setMode("detail");
                  }}
                >
                  <img
                    src={asset(`/network/requests/${item.id}/image`)}
                    alt={item.title}
                  />
                  <div>
                    <span>{statusNames[item.status]}</span>
                    <h3>{item.title}</h3>
                    <p>{item.maker?.name || "Maker to be matched"}</p>
                  </div>
                  <ArrowUpRight size={18} />
                </button>
              ))
            )}
          </section>
        </>
      )}
    </div>
  );
}
