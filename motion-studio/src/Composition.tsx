import React from "react";
import { loadFont } from "@remotion/fonts";
import {
  AbsoluteFill,
  Composition,
  Easing,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  type InteractivitySchema,
} from "remotion";

await Promise.all([
  loadFont({
    family: "StudioFa",
    url: staticFile("fonts/StudioFa-Regular.ttf"),
    weight: "400",
  }),
  loadFont({
    family: "StudioFa",
    url: staticFile("fonts/StudioFa-Bold.ttf"),
    weight: "700",
  }),
]);

// The page instances below are independently editable in Studio. Their browser chrome is decorative.
type PageProps = {
  title: string;
  category: string;
  accent: string;
  linked: boolean;
  style?: React.CSSProperties;
};
const PageInner: React.FC<PageProps> = ({
  title,
  category,
  accent,
  linked,
  style,
}) => (
  <Interactive.Div
    style={{
      position: "absolute",
      width: 400,
      height: 300,
      borderRadius: 26,
      background: "#fffdf8",
      border: "2px solid #d8d4cb",
      boxShadow: "0 16px 0 #d8d4cb, 0 26px 55px #25221b12",
      fontFamily: "StudioFa",
      color: "#242820",
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        height: 47,
        borderBottom: "2px solid #e7e2d9",
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "0 22px",
        background: "#f7f4ed",
      }}
    >
      <div
        style={{ width: 9, height: 9, borderRadius: "50%", background: accent }}
      />
      <div
        style={{
          width: 9,
          height: 9,
          borderRadius: "50%",
          background: "#d6d2ca",
        }}
      />
      <div
        style={{
          width: 9,
          height: 9,
          borderRadius: "50%",
          background: "#d6d2ca",
        }}
      />
      <div
        style={{
          marginLeft: 20,
          fontFamily: "monospace",
          fontSize: 15,
          color: "#777b70",
        }}
      >
        3eo.example / learn
      </div>
    </div>
    <div dir="rtl" style={{ padding: "22px 27px" }}>
      <div style={{ fontSize: 22, color: accent, marginBottom: 10 }}>
        {category}
      </div>
      <div
        style={{
          fontSize: 44,
          fontWeight: 700,
          letterSpacing: -1.6,
          whiteSpace: "nowrap",
        }}
      >
        {title}
      </div>
      <div
        style={{
          height: 9,
          width: "95%",
          background: "#e9e6df",
          borderRadius: 8,
          marginTop: 23,
        }}
      />
      <div
        style={{
          height: 9,
          width: "72%",
          background: "#e9e6df",
          borderRadius: 8,
          marginTop: 12,
        }}
      />
      {linked ? (
        <div
          style={{
            fontSize: 26,
            color: accent,
            textDecoration: "underline",
            textUnderlineOffset: 7,
            marginTop: 18,
          }}
        >
          راهنمای کلمات کلیدی ↗
        </div>
      ) : (
        <div
          style={{
            width: 75,
            height: 9,
            background: accent,
            borderRadius: 8,
            marginTop: 25,
          }}
        />
      )}
    </div>
  </Interactive.Div>
);
const pageSchema = {
  title: { type: "text-content", default: "", description: "عنوان صفحه" },
  category: { type: "text-content", default: "", description: "نوع صفحه" },
  accent: { type: "color", default: "#d65a3e", description: "رنگ تأکید" },
  linked: { type: "boolean", default: false, description: "نمایش لینک مرتبط" },
} as const satisfies InteractivitySchema;
export const PageCard = Interactive.withSchema({
  Component: PageInner,
  componentName: "<PageCard>",
  schema: pageSchema,
  wrapInSequence: true,
});

export const InternalLinks: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  // A deterministic cubic path: the light packet follows the actual drawn edge.
  const travel = interpolate(frame, [8.1 * fps, 10.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const packetX =
    (1 - travel) ** 3 * 540 +
    3 * (1 - travel) ** 2 * travel * 540 +
    3 * (1 - travel) * travel ** 2 * 250 +
    travel ** 3 * 250;
  const packetY =
    (1 - travel) ** 3 * 360 +
    3 * (1 - travel) ** 2 * travel * 500 +
    3 * (1 - travel) * travel ** 2 * 500 +
    travel ** 3 * 650;
  return (
    <AbsoluteFill
      style={{
        background: "#f0ede5",
        color: "#252a23",
        fontFamily: "StudioFa",
        overflow: "hidden",
      }}
    >
      <AbsoluteFill
        style={{
          backgroundImage:
            "radial-gradient(#92978335 1.4px, transparent 1.4px)",
          backgroundSize: "34px 34px",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 850,
          height: 850,
          left: -300,
          top: 400,
          background: "radial-gradient(circle, #e6b6a044, transparent 68%)",
        }}
      />
      <Interactive.Div
        name="Brand"
        style={{
          position: "absolute",
          left: 88,
          top: 100,
          fontSize: 30,
          fontWeight: 700,
          letterSpacing: 4,
        }}
      >
        3EO <span style={{ color: "#d65a3e" }}>STUDIO</span>
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          right: 88,
          top: 101,
          fontSize: 23,
          color: "#72786b",
        }}
      >
        SEO / 01
      </div>

      <Interactive.Div
        name="Question"
        dir="rtl"
        premountFor={fps}
        durationInFrames={4 * fps}
        style={{
          position: "absolute",
          top: 205,
          right: 90,
          left: 90,
          fontWeight: 700,
          fontSize: 87,
          lineHeight: 1.5,
          letterSpacing: -4,
          opacity: interpolate(
            frame,
            [0, 0.5 * fps, 3.1 * fps, 3.6 * fps],
            [0, 1, 1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
          translate: interpolate(
            frame,
            [0, 0.8 * fps],
            ["0px 45px", "0px 0px"],
            {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            },
          ),
        }}
      >
        هر صفحه،
        <br />
        یک جزیره؟
      </Interactive.Div>
      <Interactive.Div
        name="Mechanism title"
        dir="rtl"
        premountFor={fps}
        from={3.2 * fps}
        durationInFrames={8.8 * fps}
        style={{
          position: "absolute",
          top: 205,
          right: 90,
          left: 90,
          fontWeight: 700,
          fontSize: 87,
          lineHeight: 1.5,
          letterSpacing: -4,
          opacity: interpolate(
            frame,
            [3.2 * fps, 3.8 * fps, 11.1 * fps, 11.7 * fps],
            [0, 1, 1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
          translate: interpolate(
            frame,
            [3.2 * fps, 4 * fps],
            ["0px 35px", "0px 0px"],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            },
          ),
        }}
      >
        با لینک داخلی
        <br />
        <span style={{ color: "#d65a3e" }}>مسیر بساز.</span>
      </Interactive.Div>
      <Interactive.Div
        name="Takeaway"
        dir="rtl"
        premountFor={fps}
        from={11.7 * fps}
        style={{
          position: "absolute",
          top: 205,
          right: 90,
          left: 90,
          fontWeight: 700,
          fontSize: 84,
          lineHeight: 1.5,
          letterSpacing: -4,
          opacity: interpolate(frame, [11.7 * fps, 12.3 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        مخاطب را به
        <br />
        <span style={{ color: "#426c54" }}>قدم بعدی برسان.</span>
      </Interactive.Div>

      <Interactive.Div
        name="Camera and site architecture"
        style={{
          position: "absolute",
          top: 530,
          left: 0,
          width: 1080,
          height: 1060,
          transformOrigin: "540px 500px",
          scale: interpolate(
            frame,
            [0, 3 * fps, 6.8 * fps, 8 * fps, 10.5 * fps, 12.4 * fps],
            [0.84, 0.9, 0.9, 0.97, 0.97, 0.9],
            {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.45, 0, 0.2, 1),
            },
          ),
          translate: interpolate(
            frame,
            [0, 6.8 * fps, 8 * fps, 10.5 * fps, 12.4 * fps],
            ["0px 45px", "0px 0px", "0px -25px", "0px -25px", "0px 15px"],
            {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.45, 0, 0.2, 1),
            },
          ),
        }}
      >
        <Interactive.Svg
          name="Drawn internal links"
          width={1080}
          height={1060}
          viewBox="0 0 1080 1060"
          style={{ position: "absolute", inset: 0, overflow: "visible" }}
        >
          <path
            d="M 540 360 C 540 500 250 500 250 650"
            fill="none"
            stroke="#d7d7ca"
            strokeWidth={5}
            strokeDasharray="10 14"
            opacity={interpolate(frame, [3.2 * fps, 3.8 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          />
          <path
            d="M 540 360 C 540 500 830 500 830 650"
            fill="none"
            stroke="#d7d7ca"
            strokeWidth={5}
            strokeDasharray="10 14"
            opacity={interpolate(frame, [3.2 * fps, 3.8 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          />
          <Interactive.Path
            name="Primary internal link"
            d="M 540 360 C 540 500 250 500 250 650"
            pathLength={1}
            fill="none"
            stroke="#d65a3e"
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={1}
            style={{
              strokeDashoffset: interpolate(
                frame,
                [3.8 * fps, 5.4 * fps],
                [1, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.6, 0, 0.2, 1),
                },
              ),
            }}
          />
          <Interactive.Path
            name="Related topic link"
            d="M 540 360 C 540 500 830 500 830 650"
            pathLength={1}
            fill="none"
            stroke="#426c54"
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={1}
            style={{
              strokeDashoffset: interpolate(
                frame,
                [4.8 * fps, 6.4 * fps],
                [1, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.6, 0, 0.2, 1),
                },
              ),
            }}
          />
          <circle
            cx={packetX}
            cy={packetY}
            r={19}
            fill="#d65a3e"
            stroke="#fff9ea"
            strokeWidth={7}
            opacity={t >= 8.1 && t <= 10.2 ? 1 : 0}
          />
          <circle
            cx={250}
            cy={650}
            r={interpolate(frame, [10.1 * fps, 10.9 * fps], [16, 72], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
            fill="none"
            stroke="#d65a3e"
            strokeWidth={4}
            opacity={interpolate(
              frame,
              [10 * fps, 10.15 * fps, 10.9 * fps],
              [0, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            )}
          />
        </Interactive.Svg>
        <PageCard
          name="Pillar article"
          title="راهنمای سئو"
          category="صفحهٔ اصلی موضوع"
          accent="#d65a3e"
          linked={true}
          premountFor={fps}
          style={{
            left: 340,
            top: 60,
            opacity: interpolate(frame, [0, 0.7 * fps], [0, 1], {
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [0, 1.1 * fps],
              ["0px 110px", "0px 0px"],
              {
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            rotate: interpolate(frame, [0, 1.1 * fps], ["-7deg", "0deg"], {
              extrapolateRight: "clamp",
            }),
          }}
        />
        <PageCard
          name="Keyword research article"
          title="کلمات کلیدی"
          category="مقالهٔ مرتبط"
          accent="#d65a3e"
          linked={false}
          premountFor={fps}
          from={0.5 * fps}
          style={{
            left: 50,
            top: 650,
            opacity: interpolate(frame, [0.5 * fps, 1.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [0.5 * fps, 1.5 * fps],
              ["-160px 100px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            rotate: interpolate(
              frame,
              [0.5 * fps, 1.5 * fps],
              ["-9deg", "-3deg"],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        />
        <PageCard
          name="Link building article"
          title="لینک‌سازی"
          category="مقالهٔ مرتبط"
          accent="#426c54"
          linked={false}
          premountFor={fps}
          from={0.8 * fps}
          style={{
            left: 630,
            top: 650,
            opacity: interpolate(frame, [0.8 * fps, 1.5 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [0.8 * fps, 1.8 * fps],
              ["160px 100px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            rotate: interpolate(
              frame,
              [0.8 * fps, 1.8 * fps],
              ["9deg", "3deg"],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        />
        <Interactive.Div
          name="Meaning of the connection"
          dir="rtl"
          premountFor={fps}
          from={5.8 * fps}
          style={{
            position: "absolute",
            left: 240,
            top: 470,
            background: "#252a23",
            color: "#fffaf0",
            borderRadius: 60,
            padding: "18px 34px",
            fontSize: 39,
            boxShadow: "0 12px 25px #25221b18",
            opacity: interpolate(
              frame,
              [5.8 * fps, 6.3 * fps, 7.1 * fps, 7.6 * fps],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          ارتباط موضوعی، نه لینک تصادفی
        </Interactive.Div>
        <Interactive.Div
          name="Cursor"
          premountFor={fps}
          from={6.7 * fps}
          durationInFrames={2.5 * fps}
          style={{
            position: "absolute",
            left: 570,
            top: 318,
            translate: interpolate(
              frame,
              [6.7 * fps, 7.7 * fps, 8.3 * fps],
              ["260px 160px", "0px 0px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.22, 1, 0.36, 1),
              },
            ),
            scale: interpolate(
              frame,
              [7.7 * fps, 7.9 * fps, 8.1 * fps],
              [1, 0.75, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
            opacity: interpolate(
              frame,
              [6.7 * fps, 7 * fps, 8.5 * fps, 9 * fps],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          <svg width="68" height="84" viewBox="0 0 68 84">
            <path
              d="M 8 5 L 57 49 L 35 53 L 47 75 L 33 82 L 21 59 L 7 76 Z"
              fill="#252a23"
              stroke="#fffaf0"
              strokeWidth="5"
              strokeLinejoin="round"
            />
          </svg>
        </Interactive.Div>
        <Interactive.Div
          name="Destination highlight"
          premountFor={fps}
          from={10.05 * fps}
          style={{
            position: "absolute",
            left: 22,
            top: 627,
            width: 456,
            height: 350,
            border: "5px solid #d65a3e",
            borderRadius: 38,
            rotate: "-3deg",
            opacity: interpolate(
              frame,
              [10.05 * fps, 10.35 * fps, 11.7 * fps, 12.4 * fps],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        />
      </Interactive.Div>
      <Interactive.Div
        name="Bottom principle"
        dir="rtl"
        style={{
          position: "absolute",
          bottom: 190,
          right: 90,
          left: 90,
          fontSize: 43,
          textAlign: "right",
          opacity: interpolate(frame, [1.5 * fps, 2.2 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        یک لینک مرتبط؛ یک مسیر روشن‌تر.
      </Interactive.Div>
      <div
        dir="rtl"
        style={{
          position: "absolute",
          bottom: 118,
          right: 90,
          fontSize: 24,
          color: "#72786b",
        }}
      >
        مثال شماتیک آموزشی • بدون ادعای تضمین رتبه
      </div>
      <div
        style={{
          position: "absolute",
          left: 90,
          bottom: 72,
          width: 900,
          height: 5,
          background: "#d9d8ce",
        }}
      >
        <div
          style={{
            height: 5,
            width: interpolate(frame, [0, 15 * fps], ["0%", "100%"]),
            background: "#d65a3e",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const MyComposition = () => (
  <>
    <Composition
      id="InternalLinks"
      component={InternalLinks}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={450}
    />
    <Composition
      id="PageCard"
      component={PageCard}
      width={560}
      height={450}
      fps={30}
      durationInFrames={90}
      defaultProps={{
        title: "راهنمای سئو",
        category: "صفحهٔ اصلی موضوع",
        accent: "#d65a3e",
        linked: true,
        style: { left: 80, top: 60 },
      }}
    />
  </>
);
