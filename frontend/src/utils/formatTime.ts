const LOCAL_TIME_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});

export function formatLocalTime(isoString: string): string {
  if (!isoString.trim()) return "--:--:--";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return LOCAL_TIME_FORMATTER.format(date);
}
