"use client";

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import {
  CASTLE_FOCUS,
  CASTLE_LABEL_STEP,
  CASTLE_SCENE_SIZE,
  spotAt,
  type HotspotMap,
  type Spot,
  type SpotId,
} from "@/castle/buildings";
import { effectiveAppearance, lightLayer, seasonByDate } from "@/castle/appearance";
import { Banner } from "@/castle/Banner";
import { Decor } from "@/castle/DecorLayer";
import { hotspotsForSeason, sceneForSeason, spotsForSeason } from "@/castle/seasons";
import { Weather } from "@/castle/Weather";
import { fitScene } from "@/castle/scene";
import type { Appearance, DecorItem } from "@/lib/v2/castle";

/** Карта зон из PNG: номер здания на пиксель. Пока не загрузилась — работают кнопки-области. */
function useHotspotMap(url: string): HotspotMap | null {
  const [loaded, setLoaded] = useState<{ url: string; map: HotspotMap } | null>(null);
  useEffect(() => {
    let cancelled = false;
    const image = new Image();
    image.onload = () => {
      if (cancelled) return;
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return;
      context.drawImage(image, 0, 0);
      const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
      const labels = new Uint8Array(canvas.width * canvas.height);
      for (let i = 0; i < labels.length; i += 1) labels[i] = Math.round(data[i * 4] / CASTLE_LABEL_STEP);
      setLoaded({ url, map: { width: canvas.width, height: canvas.height, labels } });
    };
    image.src = url;
    return () => {
      cancelled = true;
    };
  }, [url]);
  // Сменился url (другой сезон) — старая карта не подходит, ждём новую.
  return loaded?.url === url ? loaded.map : null;
}

/** Подсветка здания: вырез той же диорамы по маске силуэта — на месте, только свечение и подпись. */
function SpotHighlight({ spot, scene, active, pulse }: { spot: Spot; scene: string; active: boolean; pulse: boolean }) {
  const { left, top, width, height } = spot.area;
  const shown = active || pulse;
  return (
    <div
      aria-hidden
      className={[
        "pointer-events-none absolute transition-opacity duration-200 ease-out motion-reduce:transition-none",
        pulse ? "castle-pulse" : "",
      ].join(" ")}
      style={{
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
        zIndex: 10 + spot.index,
        opacity: shown ? 1 : 0,
        filter: "drop-shadow(0 0 6px rgb(255 211 110 / 0.9)) drop-shadow(0 10px 12px rgb(20 10 30 / 0.45))",
      }}
    >
      <div
        className="h-full w-full"
        style={{
          backgroundImage: `url(${scene})`,
          backgroundSize: `${10000 / width}% ${10000 / height}%`,
          backgroundPosition: `${(left / (100 - width)) * 100}% ${(top / (100 - height)) * 100}%`,
          WebkitMaskImage: `url(${spot.mask})`,
          maskImage: `url(${spot.mask})`,
          WebkitMaskSize: "100% 100%",
          maskSize: "100% 100%",
          filter: "brightness(1.14) saturate(1.06)",
        }}
      />
      <span
        className="mat-brass absolute left-1/2 -translate-x-1/2 -translate-y-[calc(100%+4px)] whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-extrabold leading-none shadow-lg lg:text-[13px]"
        style={{ top: `${spot.labelTop}%` }}
      >
        {spot.title}
      </span>
    </div>
  );
}

/** Где на экране лежит диорама: замок вписан в свободную область `freeArea`, пейзаж — на весь экран. */
function useSceneFit(freeArea: HTMLElement | null) {
  const [fit, setFit] = useState<{ scale: number; left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const update = () => {
      const free = freeArea?.getBoundingClientRect();
      if (!free) return;
      setFit(
        fitScene(
          { width: window.innerWidth, height: window.innerHeight },
          { left: free.left, top: free.top, width: free.width, height: free.height },
          CASTLE_SCENE_SIZE,
          CASTLE_FOCUS,
        ),
      );
    };
    update();
    const observer = new ResizeObserver(update);
    if (freeArea) observer.observe(freeArea);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [freeArea]);
  return fit;
}

/** Если диорама не закрывает экран по высоте — края растворяются в размытой подложке, без резкой границы. */
const EDGE_FADE = "linear-gradient(to bottom, transparent, #000 12%, #000 88%, transparent)";

/** Сцена замка на весь экран: одна картинка, здание под курсором/пальцем — по карте зон. */
export function CastleStage({
  freeArea,
  openId,
  pulsing,
  appearance,
  decor,
  emblem,
  onOpen,
}: {
  freeArea: HTMLElement | null;
  openId: SpotId | null;
  pulsing: SpotId[];
  appearance: Appearance | null;
  decor: DecorItem[];
  emblem: string;
  onOpen: (id: SpotId) => void;
}) {
  const season = appearance?.season ?? seasonByDate(new Date());
  const scene = sceneForSeason(season);
  const spots = spotsForSeason(season);
  const map = useHotspotMap(hotspotsForSeason(season));
  const fit = useSceneFit(freeArea);
  const sceneRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<SpotId | null>(null);
  const [focused, setFocused] = useState<SpotId | null>(null);

  const covers =
    !!fit &&
    typeof window !== "undefined" &&
    fit.top <= 0 &&
    fit.top + CASTLE_SCENE_SIZE.height * fit.scale >= window.innerHeight;

  const pointAt = (clientX: number, clientY: number): SpotId | null => {
    const rect = sceneRef.current?.getBoundingClientRect();
    if (!map || !rect) return null;
    return spotAt(map, (clientX - rect.left) / rect.width, (clientY - rect.top) / rect.height);
  };

  return (
    <div className="fixed inset-0 z-0 overflow-hidden bg-[#1a1230]">
      {/* Подложка на случай узкого экрана, где картинка не закрывает всё */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={scene} alt="" aria-hidden className="absolute inset-0 h-full w-full scale-110 object-cover blur-2xl" />
      {fit ? (
        <div
          ref={sceneRef}
          className="absolute touch-manipulation select-none"
          style={{
            left: fit.left,
            top: fit.top,
            width: CASTLE_SCENE_SIZE.width * fit.scale,
            height: CASTLE_SCENE_SIZE.height * fit.scale,
            cursor: hovered ? "pointer" : "default",
          }}
          onPointerMove={(event) => {
            if (event.pointerType === "mouse") setHovered(pointAt(event.clientX, event.clientY));
          }}
          onPointerLeave={() => setHovered(null)}
          onClick={(event) => {
            const id = pointAt(event.clientX, event.clientY);
            if (id) onOpen(id);
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={scene}
            alt="Замок Фоксинбург"
            draggable={false}
            className="absolute inset-0 h-full w-full"
            style={covers ? undefined : { WebkitMaskImage: EDGE_FADE, maskImage: EDGE_FADE }}
          />
          {appearance ? (
            <>
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={lightLayer(effectiveAppearance(appearance, new Date()).time) as CSSProperties}
              />
              <Decor items={decor} time={effectiveAppearance(appearance, new Date()).time} />
              <Banner color={appearance.banner_color} emblem={emblem} />
              <Weather kind={effectiveAppearance(appearance, new Date()).weather} />
            </>
          ) : null}
          {spots.map((spot) => (
            <SpotHighlight
              key={spot.id}
              spot={spot}
              scene={scene}
              active={hovered === spot.id || focused === spot.id || openId === spot.id}
              pulse={pulsing.includes(spot.id)}
            />
          ))}
          {/* Клавиатура и скринридеры: кнопки по областям зданий, мышь их не перехватывает. */}
          {spots.map((spot) => (
            <button
              key={spot.id}
              type="button"
              aria-label={`${spot.title} — ${spot.hint}`}
              data-spot={spot.id}
              className="pointer-events-none absolute rounded-xl opacity-0 focus-visible:outline-none"
              style={{ left: `${spot.area.left}%`, top: `${spot.area.top}%`, width: `${spot.area.width}%`, height: `${spot.area.height}%` }}
              onFocus={() => setFocused(spot.id)}
              onBlur={() => setFocused(null)}
              onClick={(event) => {
                event.stopPropagation();
                onOpen(spot.id);
              }}
            />
          ))}
        </div>
      ) : null}
      {/* Мягкое затемнение краёв под заголовком и лентой */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "linear-gradient(to bottom, rgb(26 18 48 / 0.55), transparent 22%, transparent 72%, rgb(26 18 48 / 0.6))" }}
      />
    </div>
  );
}
