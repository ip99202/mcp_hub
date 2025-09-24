import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// Tailwind 클래스 병합 유틸리티 (중복/충돌 클래스 정리)
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
