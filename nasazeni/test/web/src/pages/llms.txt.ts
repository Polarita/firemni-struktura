import type { APIRoute } from "astro";

export const GET: APIRoute = () => new Response(
  "# Polarita s.r.o.\n\n> Elektro správa objektů pro SVJ a firmy. Soukromý náhled TEST.\n\n" +
  "## Služby\n\n" +
  `- [Ceník](${import.meta.env.BASE_URL}#cenik): měsíční tarify a rozsah instalací.\n` +
  `- [Kalkulačka SVJ](${import.meta.env.BASE_URL}kalkulacka-svj/): roční úspora a PDF na schůzi výboru.\n` +
  `- [Převzetí šanonů](${import.meta.env.BASE_URL}prevzeti-sanonu/): postup předání PDF ke spisu.\n`
);
