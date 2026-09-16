"use client";

import { useState } from "react";

import { contentImage } from "@/lib/v2/media";

type ContentImageProps = { path: string | null | undefined; alt: string; className?: string; fallback?: string };

/** Картинка слова. Пока файла нет — аккуратная подпись вместо сломанной картинки. */
export function ContentImage({ path, alt, className = "", fallback }: ContentImageProps) {
  const [broken, setBroken] = useState(false);
  const src = contentImage(path);
  if (!src || broken) {
    return (
      <span className={`flex items-center justify-center rounded-xl bg-grid/70 text-center font-extrabold text-royal ${className}`}>
        {fallback ?? alt}
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element -- контентные webp уже оптимизированы конвейером
  return <img src={src} alt={alt} className={`object-contain ${className}`} onError={() => setBroken(true)} draggable={false} />;
}
