import { ImageResponse } from "next/og";

// The link preview: the headline and the stage sequence the product draws,
// with grounding as the probable cause.

export const alt = "TraceroAI: know which stage of your RAG pipeline failed.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const STAGES = [
  { name: "Retrieval", state: "Passed", color: "#1d7348" },
  { name: "Grounding", state: "Failed", color: "#b42318" },
  { name: "Answer", state: "Passed", color: "#1d7348" },
];

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#ffffff",
          color: "#14202e",
          padding: "72px 80px",
          borderTop: "12px solid #1d3a5f",
        }}
      >
        <div style={{ display: "flex", fontSize: 30, fontWeight: 700 }}>TraceroAI</div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 76, fontWeight: 700, lineHeight: 1.05, letterSpacing: -2, maxWidth: 900 }}>
            Know which stage of your RAG pipeline failed.
          </div>
          <div style={{ display: "flex", marginTop: 48, border: "2px solid #c5ccd6" }}>
            {STAGES.map((stage, i) => (
              <div
                key={stage.name}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  flex: 1,
                  padding: "22px 26px",
                  borderLeft: i === 0 ? "none" : "2px solid #dfe4ea",
                  borderTop: `8px solid ${stage.color}`,
                  background: stage.state === "Failed" ? "#fdecea" : "#ffffff",
                }}
              >
                <div style={{ display: "flex", fontSize: 30, fontWeight: 600 }}>{stage.name}</div>
                <div style={{ display: "flex", fontSize: 26, color: stage.color, fontWeight: 600, marginTop: 6 }}>
                  {stage.state}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", fontSize: 26, color: "#4f5a6b" }}>
          Open-source tracing and evaluation for RAG · self-hosted · Apache-2.0
        </div>
      </div>
    ),
    size,
  );
}
