export function BrandMark({
  href,
  onClick,
}: {
  href?: string;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <svg className="mark" viewBox="0 0 100 100" aria-hidden="true">
        <rect x="4" y="4" width="92" height="92" rx="26" fill="#4F6FE8" />
        <path
          d="M50 80 V54 M50 54 L31 30 M50 54 L64 37"
          stroke="#fff"
          strokeWidth="10"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <path
          className="spark"
          d="M72 15 L75.5 25.5 L86 29 L75.5 32.5 L72 43 L68.5 32.5 L58 29 L68.5 25.5 Z"
          fill="#F2B84B"
        />
      </svg>
      <span>
        campus<b>yamu</b>
      </span>
    </>
  );

  if (href) {
    return (
      <a
        className="brand"
        href={href}
        aria-label="CampusYamu"
        onClick={(e) => {
          if (onClick) {
            e.preventDefault();
            onClick();
          }
        }}
      >
        {inner}
      </a>
    );
  }

  return (
    <span className="brand" aria-label="CampusYamu">
      {inner}
    </span>
  );
}

export const ArrowRightIcon = () => (
  <svg
    className="arr"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const BackIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M15 18l-6-6 6-6" />
  </svg>
);
