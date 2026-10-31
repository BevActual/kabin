type Option<T extends string> = {
  id: T;
  label: string;
};

type Props<T extends string> = {
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
  label: string;
};

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  label,
}: Props<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-grouped p-0.5"
    >
      {options.map((option) => {
        const selected = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.id)}
            className={`rounded-[8px] px-3 py-1 text-[calc(13px*var(--kabin-type-scale))] font-medium transition-colors duration-[var(--kabin-motion-fast)] ${
              selected
                ? "kabin-segment-selected text-kabin-primary"
                : "text-kabin-secondary hover:text-kabin-primary"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
