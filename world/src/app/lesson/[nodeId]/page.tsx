"use client";

import { useParams } from "next/navigation";

import { LessonScreen } from "@/features/lesson/LessonScreen";

export default function LessonPage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  return <LessonScreen key={nodeId} nodeId={nodeId} />;
}
