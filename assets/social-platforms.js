(() => {
  "use strict";

  const ORDER = [
    "twitch", "youtube", "instagram", "x", "twitter", "tiktok",
    "discord", "kick", "facebook", "snapchat", "telegram", "whatsapp",
    "linkedin", "threads", "bluesky", "reddit",
  ];
  const SIMPLE_ICONS_VERSION = "16.28.0";
  const PLATFORMS = {
    twitch:    { name: "Twitch", color: "#9146ff", source: "simple-icons", path: "M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z" },
    youtube:   { name: "YouTube", color: "#ff0000", source: "simple-icons", path: "M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" },
    instagram: {
      name: "Instagram",
      color: "#e1306c",
      source: "simple-icons",
      path: "M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077",
      grouped: {
        cssGradient: "linear-gradient(145deg,#4f5bd5 0%,#962fbf 28%,#d62976 52%,#fa7e1e 76%,#feda75 100%)",
        gradient: [[0,"#4f5bd5"],[.28,"#962fbf"],[.52,"#d62976"],[.76,"#fa7e1e"],[1,"#feda75"]],
        details: [
          { d: "M8 5h8a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3z", stroke: 1.8 },
          { d: "M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z", stroke: 1.8 },
          { d: "M17.25 6.35a1.15 1.15 0 1 1 0 2.3 1.15 1.15 0 0 1 0-2.3z", fill: true },
        ],
        path: "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5z",
      },
    },
    x:         { name: "X", color: "#101014", bare: "#ffffff", source: "simple-icons", path: "M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z" },
    twitter:   { name: "Twitter", color: "#1d9bf0", source: "fallback", path: "M22 5.9c-.7.3-1.5.5-2.3.6a4 4 0 0 0 1.8-2.2c-.8.5-1.7.8-2.6 1a4 4 0 0 0-6.9 3.7A11.4 11.4 0 0 1 3.8 4.6a4 4 0 0 0 1.2 5.4c-.6 0-1.2-.2-1.8-.5a4 4 0 0 0 3.2 4 4 4 0 0 1-1.8.1 4 4 0 0 0 3.7 2.8A8 8 0 0 1 2 18.1a11.3 11.3 0 0 0 6.1 1.8c7.4 0 11.4-6.1 11.4-11.4v-.5c.8-.6 1.5-1.3 2-2.1z" },
    tiktok:    { name: "TikTok", color: "#25f4ee", surface: "#f6f7fb", ink: "#101014", source: "simple-icons", layers: [{ color: "#25f4ee", dx: -1.15, dy: -.7 }, { color: "#fe2c55", dx: 1.15, dy: .7 }, { color: "#101014", bareColor: "#ffffff" }], path: "M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" },
    discord:   { name: "Discord", color: "#5865f2", source: "simple-icons", path: "M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" },
    kick:      { name: "Kick", color: "#53fc18", ink: "#101014", source: "simple-icons", path: "M1.333 0h8v5.333H12V2.667h2.667V0h8v8H20v2.667h-2.667v2.666H20V16h2.667v8h-8v-2.667H12v-2.666H9.333V24h-8Z" },
    facebook:  { name: "Facebook", color: "#1877f2", source: "simple-icons", path: "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z" },
    snapchat:  { name: "Snapchat", color: "#fffc00", ink: "#101014", source: "simple-icons", grouped: { tileInk: "#ffffff", tileStroke: "#101014" }, path: "M12.206.793c.99 0 4.347.276 5.93 3.821.529 1.193.403 3.219.299 4.847l-.003.06c-.012.18-.022.345-.03.51.075.045.203.09.401.09.3-.016.659-.12 1.033-.301.165-.088.344-.104.464-.104.182 0 .359.029.509.09.45.149.734.479.734.838.015.449-.39.839-1.213 1.168-.089.029-.209.075-.344.119-.45.135-1.139.36-1.333.81-.09.224-.061.524.12.868l.015.015c.06.136 1.526 3.475 4.791 4.014.255.044.435.27.42.509 0 .075-.015.149-.045.225-.24.569-1.273.988-3.146 1.271-.059.091-.12.375-.164.57-.029.179-.074.36-.134.553-.076.271-.27.405-.555.405h-.03c-.135 0-.313-.031-.538-.074-.36-.075-.765-.135-1.273-.135-.3 0-.599.015-.913.074-.6.104-1.123.464-1.723.884-.853.599-1.826 1.288-3.294 1.288-.06 0-.119-.015-.18-.015h-.149c-1.468 0-2.427-.675-3.279-1.288-.599-.42-1.107-.779-1.707-.884-.314-.045-.629-.074-.928-.074-.54 0-.958.089-1.272.149-.211.043-.391.074-.54.074-.374 0-.523-.224-.583-.42-.061-.192-.09-.389-.135-.567-.046-.181-.105-.494-.166-.57-1.918-.222-2.95-.642-3.189-1.226-.031-.063-.052-.15-.055-.225-.015-.243.165-.465.42-.509 3.264-.54 4.73-3.879 4.791-4.02l.016-.029c.18-.345.224-.645.119-.869-.195-.434-.884-.658-1.332-.809-.121-.029-.24-.074-.346-.119-1.107-.435-1.257-.93-1.197-1.273.09-.479.674-.793 1.168-.793.146 0 .27.029.383.074.42.194.789.3 1.104.3.234 0 .384-.06.465-.105l-.046-.569c-.098-1.626-.225-3.651.307-4.837C7.392 1.077 10.739.807 11.727.807l.419-.015h.06z" },
    telegram:  { name: "Telegram", color: "#2aabee", source: "simple-icons", path: "M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" },
    whatsapp:  { name: "WhatsApp", color: "#25d366", source: "simple-icons", path: "M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" },
    linkedin:  { name: "LinkedIn", color: "#0a66c2", source: "fallback", path: "M4.9 3.5a2.4 2.4 0 1 1 0 4.9 2.4 2.4 0 0 1 0-4.9zM3 9.5h4v11H3zm7 0h3.8v1.5h.1a4.2 4.2 0 0 1 3.8-2c4 0 4.8 2.6 4.8 6v5.5h-4v-4.9c0-1.2 0-2.7-1.7-2.7s-2 1.3-2 2.6v5H10z" },
    threads:   { name: "Threads", color: "#101014", bare: "#ffffff", source: "simple-icons", path: "M18.263 11.097c-.03-3.486-1.92-5.586-5.111-5.586-2.13 0-3.922.963-4.863 2.499l2.062 1.438c.535-.843 1.272-1.543 2.628-1.543 1.528 0 2.318.85 2.544 2.431a15 15 0 0 0-2.236-.173c-4.125 0-6.068 1.867-6.068 4.336s1.943 3.99 4.804 3.99c3.139 0 5.013-2.115 5.781-4.735.798.361 1.348 1.204 1.348 2.47 0 3.387-3.907 5.232-7.22 5.232-4.885 0-8.077-3.207-8.077-8.424 0-6.392 4.223-10.487 9.9-10.487 3.808 0 5.69 1.671 6.97 3.914l2.108-1.475C21.44 2.078 18.331 0 13.663 0 6.227 0 1.168 5.277 1.168 12.934c0 7 4.953 11.066 10.856 11.066 4.878 0 9.809-2.846 9.809-7.716 0-2.545-1.46-4.231-3.569-5.187m-6.33 4.855c-1.077 0-2.026-.512-2.026-1.453 0-1.483 1.822-1.934 3.606-1.934.678 0 1.34.045 1.927.173-.422 1.927-1.671 3.215-3.508 3.214Z" },
    bluesky:   { name: "Bluesky", color: "#0085ff", source: "simple-icons", path: "M5.202 2.857C7.954 4.922 10.913 9.11 12 11.358c1.087-2.247 4.046-6.436 6.798-8.501C20.783 1.366 24 .213 24 3.883c0 .732-.42 6.156-.667 7.037-.856 3.061-3.978 3.842-6.755 3.37 4.854.826 6.089 3.562 3.422 6.299-5.065 5.196-7.28-1.304-7.847-2.97-.104-.305-.152-.448-.153-.327 0-.121-.05.022-.153.327-.568 1.666-2.782 8.166-7.847 2.97-2.667-2.737-1.432-5.473 3.422-6.3-2.777.473-5.899-.308-6.755-3.369C.42 10.04 0 4.615 0 3.883c0-3.67 3.217-2.517 5.202-1.026" },
    reddit:    { name: "Reddit", color: "#ff4500", source: "simple-icons", path: "M12 0C5.373 0 0 5.373 0 12c0 3.314 1.343 6.314 3.515 8.485l-2.286 2.286C.775 23.225 1.097 24 1.738 24H12c6.627 0 12-5.373 12-12S18.627 0 12 0Zm4.388 3.199c1.104 0 1.999.895 1.999 1.999 0 1.105-.895 2-1.999 2-.946 0-1.739-.657-1.947-1.539v.002c-1.147.162-2.032 1.15-2.032 2.341v.007c1.776.067 3.4.567 4.686 1.363.473-.363 1.064-.58 1.707-.58 1.547 0 2.802 1.254 2.802 2.802 0 1.117-.655 2.081-1.601 2.531-.088 3.256-3.637 5.876-7.997 5.876-4.361 0-7.905-2.617-7.998-5.87-.954-.447-1.614-1.415-1.614-2.538 0-1.548 1.255-2.802 2.803-2.802.645 0 1.239.218 1.712.585 1.275-.79 2.881-1.291 4.64-1.365v-.01c0-1.663 1.263-3.034 2.88-3.207.188-.911.993-1.595 1.959-1.595Zm-8.085 8.376c-.784 0-1.459.78-1.506 1.797-.047 1.016.64 1.429 1.426 1.429.786 0 1.371-.369 1.418-1.385.047-1.017-.553-1.841-1.338-1.841Zm7.406 0c-.786 0-1.385.824-1.338 1.841.047 1.017.634 1.385 1.418 1.385.785 0 1.473-.413 1.426-1.429-.046-1.017-.721-1.797-1.506-1.797Zm-3.703 4.013c-.974 0-1.907.048-2.77.135-.147.015-.241.168-.183.305.483 1.154 1.622 1.964 2.953 1.964 1.33 0 2.47-.81 2.953-1.964.057-.137-.037-.29-.184-.305-.863-.087-1.795-.135-2.769-.135Z" },
  };
  const ALIASES = {
    ig: "instagram", yt: "youtube", tt: "tiktok", fb: "facebook",
    snap: "snapchat", tg: "telegram", wa: "whatsapp", li: "linkedin",
    tweet: "twitter",
  };
  const FONTS = {
    montserrat: '"Montserrat", "Segoe UI", system-ui, sans-serif',
    poppins: '"Poppins", "Segoe UI", system-ui, sans-serif',
    archivo: '"Archivo Black", "Segoe UI", system-ui, sans-serif',
    nunito: '"Nunito", "Segoe UI", system-ui, sans-serif',
    anton: '"Anton", "Bahnschrift", system-ui, sans-serif',
    sans: '"Segoe UI", system-ui, sans-serif',
    display: '"Bahnschrift", "Segoe UI Semibold", system-ui, sans-serif',
    round: '"Fredoka", "Segoe UI", system-ui, sans-serif',
    mono: '"Cascadia Mono", Consolas, monospace',
    serif: 'Georgia, "Times New Roman", serif',
  };
  const DEFAULTS = {
    accounts: ORDER.map(platform => ({
      platform,
      enabled: ["twitch", "youtube", "instagram", "tiktok"].includes(platform),
      handle: "yourname",
    })),
    layout: "sticker", mode: "individual", sharedName: "",
    heading: "Stay connected", align: "center", iconShape: "rounded",
    iconBackground: true, size: "medium", brand: true, color: "f6f7fb",
    shellColor: "141418", textColor: "ffffff", font: "display",
    weight: 800, outline: 3, scale: 1, cycle: 4,
    rotatorShape: "capsule", transition: "slide", prefix: "@",
    timer: true, showPlatform: true,
  };
  const CHOICES = {
    layout: new Set(["sticker", "flat", "compact", "stacked", "fused"]),
    mode: new Set(["individual", "shared"]),
    align: new Set(["left", "center", "right"]),
    iconShape: new Set(["rounded", "circle", "square", "diamond", "hex"]),
    size: new Set(["small", "medium", "large"]),
    font: new Set(Object.keys(FONTS)),
    rotatorShape: new Set(["capsule", "rounded", "square", "cut"]),
    transition: new Set(["slide", "fade", "flip"]),
  };
  const ACCOUNT_LIMITS = {
    social: 8,
    "social-rotator": 12,
  };
  const clamp = (value, minimum, maximum, fallback) => {
    const numeric = Number(value);
    return Math.max(minimum, Math.min(maximum, Number.isFinite(numeric) ? numeric : fallback));
  };
  const hex = (value, fallback) => {
    const candidate = String(value || "").trim().replace(/^#/, "").toLowerCase();
    return /^[0-9a-f]{6}$/.test(candidate) ? candidate : fallback;
  };
  const choice = (value, key) => {
    const candidate = String(value || "").trim().toLowerCase();
    return CHOICES[key].has(candidate) ? candidate : DEFAULTS[key];
  };
  const bool = (value, fallback) => (
    typeof value === "boolean" ? value : fallback
  );
  const short = (value, maximum, fallback = "") => {
    const candidate = String(value ?? "").replace(/\s+/g, " ").trim();
    return (candidate || fallback).slice(0, maximum);
  };
  const contrast = value => {
    const candidate = String(value || "").replace(/^#/, "");
    if (!/^[0-9a-f]{6}$/i.test(candidate)) return "#ffffff";
    const channels = [0, 2, 4].map(offset => parseInt(candidate.slice(offset, offset + 2), 16));
    const luminance = channels[0] * .299 + channels[1] * .587 + channels[2] * .114;
    return luminance > 165 ? "#101014" : "#ffffff";
  };

  function normalizeAccounts(raw, overlayType) {
    const supplied = Array.isArray(raw) ? raw : DEFAULTS.accounts;
    const byPlatform = new Map();
    supplied.slice(0, ORDER.length).forEach(item => {
      if (!item || typeof item !== "object") return;
      const platform = String(item.platform || "").toLowerCase();
      if (!PLATFORMS[platform] || byPlatform.has(platform)) return;
      const icon = String(item.icon || "").trim();
      byPlatform.set(platform, {
        platform,
        enabled: Boolean(item.enabled),
        handle: short(String(item.handle ?? "").replace(/^@+/, ""), 64),
        icon: icon && !/^[a-z]+:/i.test(icon) && !icon.includes("..") ? icon.slice(0, 256) : "",
      });
    });
    const limit = ACCOUNT_LIMITS[overlayType] || ORDER.length;
    let enabled = 0;
    return ORDER.map(platform => {
      const account = byPlatform.get(platform) || {
        platform, enabled: false, handle: "yourname", icon: "",
      };
      let selected = account.enabled;
      if (selected && enabled >= limit) selected = false;
      if (selected) enabled += 1;
      return { ...account, enabled: selected };
    });
  }

  function normalize(raw, overlayType) {
    const source = raw && typeof raw === "object" ? raw : {};
    return {
      accounts: normalizeAccounts(source.accounts, overlayType),
      layout: choice(source.layout, "layout"),
      mode: choice(source.mode, "mode"),
      sharedName: short(source.sharedName, 64),
      heading: short(source.heading, 32, DEFAULTS.heading),
      align: choice(source.align, "align"),
      iconShape: choice(source.iconShape, "iconShape"),
      iconBackground: bool(
        source.iconBackground,
        DEFAULTS.iconBackground,
      ),
      size: choice(source.size, "size"),
      brand: bool(source.brand, DEFAULTS.brand),
      color: hex(source.color, DEFAULTS.color),
      shellColor: hex(source.shellColor, DEFAULTS.shellColor),
      textColor: hex(source.textColor, DEFAULTS.textColor),
      font: choice(source.font, "font"),
      weight: Math.round(clamp(source.weight, 300, 900, DEFAULTS.weight)),
      outline: Math.round(clamp(source.outline, 0, 8, DEFAULTS.outline)),
      scale: clamp(source.scale, .5, 2, DEFAULTS.scale),
      cycle: clamp(source.cycle, 1.5, 30, DEFAULTS.cycle),
      rotatorShape: choice(source.rotatorShape, "rotatorShape"),
      transition: choice(source.transition, "transition"),
      prefix: source.prefix === undefined
        ? DEFAULTS.prefix
        : short(source.prefix, 4),
      timer: bool(source.timer, DEFAULTS.timer),
      showPlatform: bool(source.showPlatform, DEFAULTS.showPlatform),
    };
  }

  function queryOverrides(query, overlayType) {
    const result = {};
    const accountChunks = query.get("accounts");
    const accounts = [];
    if (accountChunks !== null) {
      accountChunks.split(",").slice(0, ORDER.length).forEach(chunk => {
        const parts = chunk.split(":").map(part => part.trim());
        const platform = ALIASES[(parts[0] || "").toLowerCase()] || (parts[0] || "").toLowerCase();
        if (!PLATFORMS[platform]) return;
        accounts.push({
          platform, enabled: true, handle: parts[1] || "", icon: parts[2] || "",
        });
      });
    } else {
      ORDER.forEach(platform => {
        const handle = query.get(platform);
        if (handle !== null) accounts.push({ platform, enabled: true, handle });
      });
    }
    if (accounts.length) {
      result.accounts = ORDER.map(platform => (
        accounts.find(account => account.platform === platform)
        || { platform, enabled: false, handle: "yourname" }
      ));
    }
    const scalarKeys = [
      "layout", "mode", "sharedName", "heading", "align", "iconShape",
      "size", "color", "shellColor", "textColor", "font", "weight",
      "outline", "scale", "cycle", "rotatorShape", "transition", "prefix",
    ];
    scalarKeys.forEach(key => {
      if (query.has(key)) result[key] = query.get(key);
    });
    if (query.has("style") && !query.has("rotatorShape")) {
      result.rotatorShape = query.get("style") === "plain" ? "square" : query.get("style");
    }
    ["brand", "iconBackground", "timer", "showPlatform"].forEach(key => {
      if (!query.has(key)) return;
      result[key] = !["off", "false", "0"].includes(String(query.get(key)).toLowerCase());
    });
    return result;
  }

  async function load(instanceId, overlayType, query) {
    let saved = DEFAULTS;
    if (instanceId && location.protocol !== "file:") {
      try {
        const response = await fetch(`/api/config?i=${encodeURIComponent(instanceId)}`, {
          cache: "no-store",
        });
        if (response.ok) {
          const payload = await response.json();
          if (payload.social && typeof payload.social === "object") saved = payload.social;
        }
      } catch {}
    }
    const overrides = queryOverrides(query, overlayType);
    const hasQueryOverride = [
      "accounts", ...ORDER, "layout", "mode", "sharedName", "heading",
      "align", "iconShape", "iconBackground", "size", "brand", "color", "shellColor",
      "textColor", "font", "weight", "outline", "scale", "cycle",
      "rotatorShape", "transition", "prefix", "timer", "showPlatform", "style",
    ].some(key => query.has(key));
    return normalize(
      hasQueryOverride ? { ...saved, ...overrides } : saved,
      overlayType,
    );
  }

  function createVectorGlyph(meta, branded, bare) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.setAttribute("aria-hidden", "true");
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const dx = Number(meta.dx) || 0;
    const dy = Number(meta.dy) || 0;
    const scale = Number(meta.scale) || 1;
    group.setAttribute(
      "transform",
      `translate(${12 + dx} ${12 + dy}) scale(${scale}) translate(-12 -12)`,
    );
    const layers = branded && Array.isArray(meta.layers)
      ? meta.layers
      : [{}];
    layers.forEach(layer => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("fill-rule", "evenodd");
      path.setAttribute("clip-rule", "evenodd");
      path.setAttribute("d", meta.path);
      const layerColor = bare && layer.bareColor
        ? layer.bareColor
        : layer.color;
      if (layerColor) path.setAttribute("fill", layerColor);
      const layerDx = Number(layer.dx) || 0;
      const layerDy = Number(layer.dy) || 0;
      if (layerDx || layerDy) {
        path.setAttribute("transform", `translate(${layerDx} ${layerDy})`);
      }
      group.append(path);
    });
    svg.append(group);
    return svg;
  }

  function createGlyph(platform, branded = true, bare = false) {
    const meta = PLATFORMS[platform];
    if (!meta) return document.createTextNode("");
    return createVectorGlyph(meta, branded, bare);
  }

  function listen(instanceId, overlayType, onConfig) {
    const customizerMode =
      new URLSearchParams(location.search).get("customizer") === "1";
    if (customizerMode) {
      window.addEventListener("message", event => {
        if (
          event.source !== window.parent
          || event.data?.type !== "overlay-studio-draft"
          || event.data?.overlayType !== overlayType
          || String(event.data?.instanceId || "") !== instanceId
          || !event.data?.config?.social
        ) return;
        onConfig(normalize(event.data.config.social, overlayType));
      });
    }
    if (location.protocol === "file:" || !("WebSocket" in window)) return;
    const connect = () => {
      let socket;
      try {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        socket = new WebSocket(`${protocol}//${location.host}/ws`);
      } catch {
        setTimeout(connect, 2000);
        return;
      }
      socket.onmessage = event => {
        if (typeof event.data !== "string" || event.data.length > 64 * 1024) return;
        let message;
        try { message = JSON.parse(event.data); } catch { return; }
        if (
          message?.type === "config"
          && String(message.instanceId || "") === instanceId
          && message.config?.social
        ) {
          onConfig(normalize(message.config.social, overlayType));
        }
      };
      socket.onclose = () => setTimeout(connect, 2000);
    };
    connect();
  }

  function deepFreeze(value, seen = new WeakSet()) {
    if (
      value === null
      || (typeof value !== "object" && typeof value !== "function")
      || seen.has(value)
    ) return value;
    seen.add(value);
    for (const key of Reflect.ownKeys(value)) {
      deepFreeze(value[key], seen);
    }
    return Object.freeze(value);
  }

  window.OverlaySocial = deepFreeze({
    SIMPLE_ICONS_VERSION,
    ORDER,
    PLATFORMS,
    ALIASES,
    FONTS,
    DEFAULTS,
    ACCOUNT_LIMITS,
    normalize,
    load,
    createGlyph,
    contrast,
    listen,
  });
})();
