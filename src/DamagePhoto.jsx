import React, { useRef, useState, useEffect } from "react";
import { asset } from "./api";
export default function DamagePhoto({ project, box, onPoint, analysis }) {
  const image = useRef();
  const [first, setFirst] = useState(null);
  useEffect(() => setFirst(null), [project.id, analysis]);
  const click = (e) => {
    if (!onPoint) return;
    const r = e.currentTarget.getBoundingClientRect();
    const point = [
      Math.max(0.01, Math.min(0.99, (e.clientX - r.left) / r.width)),
      Math.max(0.01, Math.min(0.99, (e.clientY - r.top) / r.height)),
    ];
    if (!first) {
      setFirst(point);
      onPoint(null);
    } else {
      onPoint([
        Math.min(first[0], point[0]),
        Math.min(first[1], point[1]),
        Math.max(first[0], point[0]),
        Math.max(first[1], point[1]),
      ]);
      setFirst(null);
    }
  };
  return (
    <div
      className={"damage-photo " + (onPoint ? "editable" : "")}
      onClick={click}
    >
      <img
        ref={image}
        src={asset(`/projects/${project.id}/image`)}
        alt={project.title}
      />
      <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        {box && (
          <rect
            x={box[0]}
            y={box[1]}
            width={box[2] - box[0]}
            height={box[3] - box[1]}
            fill="#b99a4133"
            stroke="#d4a744"
            strokeWidth=".004"
          />
        )}
        {first && (
          <circle cx={first[0]} cy={first[1]} r=".012" fill="#e1bb5d" />
        )}
        {analysis?.outlines.map((line, i) => (
          <polygon
            key={i}
            points={line.map((p) => p.join(",")).join(" ")}
            fill="#c2554833"
            stroke="#d16354"
            strokeWidth=".002"
          />
        ))}
      </svg>
      {onPoint && (
        <span className="photo-hint">
          {first
            ? "Now click the opposite corner"
            : "Click two opposite corners around the damage"}
        </span>
      )}
    </div>
  );
}
