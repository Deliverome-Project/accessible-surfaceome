import { useCallback, useState } from "react";

export function useTweaks<T extends Record<string, unknown>>(defaults: T) {
  const [values, setValues] = useState<T>(defaults);
  const setTweak = useCallback(<K extends keyof T>(key: K, val: T[K]) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);
  return [values, setTweak] as const;
}
