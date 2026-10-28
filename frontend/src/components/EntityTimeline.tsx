export function EntityTimeline({
  events,
}: {
  events: Array<{ at?: string; type: string; detail?: string }>;
}) {
  return (
    <div className="relative space-y-3 pl-5">
      <div className="absolute bottom-1 left-1.5 top-1 w-px bg-slate-800" />
      {events.map((event, index) => (
        <div key={index} className="relative">
          <span className="absolute -left-[15px] top-1.5 h-2 w-2 rounded-full border border-slate-600 bg-slate-900" />
          <p className="text-xs font-medium text-slate-200">{event.type}</p>
          <p className="text-[10px] text-slate-500">
            {event.at ?? ""}
            {event.detail ? ` · ${event.detail}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}
