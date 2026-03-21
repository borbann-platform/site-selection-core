export interface ChatReferenceSeed {
  id: string | number;
  listingKey?: string;
  sourceType?: string;
  district?: string;
  style?: string;
}

export interface ChatEntityReference {
  key: string;
  label: string;
  kind: "property" | "listing";
  propertyId?: string;
  listingKey?: string;
  note?: string;
}

export interface StructuredPropertyReference {
  id: string | number;
  listing_key?: string;
  source_type?: string;
  house_ref?: string;
  locator?: string;
  price?: number;
  total_price?: number;
  district?: string;
  amphur?: string;
  subdistrict?: string;
  style?: string;
  building_style_desc?: string;
  area?: number;
  building_area?: number;
  lat?: number;
  lon?: number;
}

const CODE_BLOCK_SPLIT_RE = /(```[\s\S]*?```)/g;
const PROPERTY_MARKER_RE =
  /<!--PROPERTIES_START-->([\s\S]*?)<!--PROPERTIES_END-->/g;
const REFERENCE_MARKER_RE =
  /<!--CHAT_REFERENCES_START-->([\s\S]*?)<!--CHAT_REFERENCES_END-->/g;
const PROPERTY_ID_RE =
  /\b(?:house|property)(?:\s+(?:id|ref))?\s*[:#]?\s*(\d+)\b/gi;
const HOUSE_LOCATOR_RE = /\bhouse:(\d+)\b/gi;
const LISTING_KEY_RE =
  /\b(?:listing(?:\s+(?:key|id))?|listing_key)\s*[:=#]?\s*((?:house|scraped|market|condo):[A-Za-z0-9:_-]+)\b/gi;
const LOCATOR_RE =
  /\blocator\s*[:=]?\s*((?:listing:)?(?:house|scraped|market|condo):[A-Za-z0-9:_-]+)\b/gi;

function dedupeReferences(references: ChatEntityReference[]) {
  const seen = new Set<string>();
  const deduped: ChatEntityReference[] = [];

  for (const reference of references) {
    if (seen.has(reference.key)) {
      continue;
    }
    seen.add(reference.key);
    deduped.push(reference);
  }

  return deduped;
}

function referenceFromLocator(
  rawLocator: string,
  label: string
): ChatEntityReference | null {
  const normalized = rawLocator.startsWith("listing:")
    ? rawLocator.slice("listing:".length)
    : rawLocator;

  if (normalized.startsWith("house:")) {
    const propertyId = normalized.slice("house:".length);
    if (!propertyId) {
      return null;
    }
    return {
      key: `property:${propertyId}`,
      label,
      kind: "property",
      propertyId,
      note: `House ${propertyId}`,
    };
  }

  return {
    key: `listing:${normalized}`,
    label,
    kind: "listing",
    listingKey: normalized,
    note: normalized,
  };
}

function placeholderLink(
  references: string[],
  label: string,
  target: ChatEntityReference
) {
  const href =
    target.kind === "property"
      ? `app://property/${target.propertyId}`
      : `app://listing/${encodeURIComponent(target.listingKey || "")}`;
  const token = `@@CHAT_ENTITY_${references.length}@@`;
  references.push(`[${label}](${href})`);
  return token;
}

function applyReferencePlaceholders(segment: string) {
  const placeholders: string[] = [];
  let output = segment;

  output = output.replace(LOCATOR_RE, (match, locator) => {
    if (typeof locator !== "string") {
      return match;
    }

    const target = referenceFromLocator(locator, match.trim());
    if (!target) {
      return match;
    }

    return placeholderLink(placeholders, match.trim(), target);
  });

  output = output.replace(LISTING_KEY_RE, (match, listingKey) => {
    if (typeof listingKey !== "string") {
      return match;
    }

    return placeholderLink(placeholders, match.trim(), {
      key: `listing:${listingKey}`,
      label: match.trim(),
      kind: "listing",
      listingKey,
      note: listingKey,
    });
  });

  output = output.replace(PROPERTY_ID_RE, (match, propertyId) => {
    if (typeof propertyId !== "string") {
      return match;
    }

    return placeholderLink(placeholders, match.trim(), {
      key: `property:${propertyId}`,
      label: match.trim(),
      kind: "property",
      propertyId,
      note: `House ${propertyId}`,
    });
  });

  output = output.replace(HOUSE_LOCATOR_RE, (match, propertyId) => {
    if (typeof propertyId !== "string") {
      return match;
    }

    return placeholderLink(placeholders, match.trim(), {
      key: `property:${propertyId}`,
      label: match.trim(),
      kind: "property",
      propertyId,
      note: `House ${propertyId}`,
    });
  });

  for (const [index, link] of placeholders.entries()) {
    output = output.replace(`@@CHAT_ENTITY_${index}@@`, link);
  }

  return output;
}

function parseReferencePayload(content: string): ChatEntityReference[] {
  const references: ChatEntityReference[] = [];

  for (const match of content.matchAll(REFERENCE_MARKER_RE)) {
    const payload = match[1];
    if (!payload) {
      continue;
    }

    try {
      const parsed = JSON.parse(payload);
      if (!Array.isArray(parsed)) {
        continue;
      }

      for (const item of parsed) {
        if (!item || typeof item !== "object") {
          continue;
        }

        const kind = item.kind === "listing" ? "listing" : "property";
        const key = typeof item.key === "string" ? item.key : undefined;
        const label = typeof item.label === "string" ? item.label : undefined;
        if (!key || !label) {
          continue;
        }

        references.push({
          key,
          label,
          kind,
          propertyId:
            typeof item.property_id === "string"
              ? item.property_id
              : typeof item.propertyId === "string"
                ? item.propertyId
                : undefined,
          listingKey:
            typeof item.listing_key === "string"
              ? item.listing_key
              : typeof item.listingKey === "string"
                ? item.listingKey
                : undefined,
          note: typeof item.note === "string" ? item.note : undefined,
        });
      }
    } catch {}
  }

  return references;
}

export function parseStructuredPropertyReferences(
  content: string
): StructuredPropertyReference[] {
  const properties: StructuredPropertyReference[] = [];

  for (const match of content.matchAll(PROPERTY_MARKER_RE)) {
    const payload = match[1];
    if (!payload) {
      continue;
    }

    try {
      const parsed = JSON.parse(payload);
      if (!Array.isArray(parsed)) {
        continue;
      }

      for (const item of parsed) {
        if (!item || typeof item !== "object") {
          continue;
        }

        const propertyId =
          typeof item.id === "string" || typeof item.id === "number"
            ? item.id
            : undefined;
        if (propertyId === undefined) {
          continue;
        }

        properties.push({
          id: propertyId,
          listing_key:
            typeof item.listing_key === "string" ? item.listing_key : undefined,
          source_type:
            typeof item.source_type === "string" ? item.source_type : undefined,
          house_ref:
            typeof item.house_ref === "string" ? item.house_ref : undefined,
          locator: typeof item.locator === "string" ? item.locator : undefined,
          price: typeof item.price === "number" ? item.price : undefined,
          total_price:
            typeof item.total_price === "number" ? item.total_price : undefined,
          district:
            typeof item.district === "string" ? item.district : undefined,
          amphur: typeof item.amphur === "string" ? item.amphur : undefined,
          subdistrict:
            typeof item.subdistrict === "string" ? item.subdistrict : undefined,
          style: typeof item.style === "string" ? item.style : undefined,
          building_style_desc:
            typeof item.building_style_desc === "string"
              ? item.building_style_desc
              : undefined,
          area: typeof item.area === "number" ? item.area : undefined,
          building_area:
            typeof item.building_area === "number" ? item.building_area : undefined,
          lat: typeof item.lat === "number" ? item.lat : undefined,
          lon: typeof item.lon === "number" ? item.lon : undefined,
        });
      }
    } catch {}
  }

  return properties;
}

export function stripStructuredChatMarkers(content: string) {
  return content
    .replace(PROPERTY_MARKER_RE, "")
    .replace(REFERENCE_MARKER_RE, "")
    .trim();
}

export function decorateMarkdownWithEntityLinks(content: string) {
  return content
    .split(CODE_BLOCK_SPLIT_RE)
    .map((segment) =>
      segment.startsWith("```") ? segment : applyReferencePlaceholders(segment)
    )
    .join("");
}

export function extractChatEntityReferences(
  content: string,
  seeds: ChatReferenceSeed[] = []
) {
  const references: ChatEntityReference[] = parseReferencePayload(content);
  const cleanedContent = stripStructuredChatMarkers(content);

  for (const seed of seeds) {
    if (seed.listingKey) {
      references.push({
        key: `listing:${seed.listingKey}`,
        label: seed.style ? `${seed.style} · ${seed.listingKey}` : seed.listingKey,
        kind: "listing",
        listingKey: seed.listingKey,
        note: seed.district,
      });
    }

    references.push({
      key: `property:${seed.id}`,
      label: seed.style ? `${seed.style} · property ${seed.id}` : `Property ${seed.id}`,
      kind: "property",
      propertyId: String(seed.id),
      note: seed.district,
    });
  }

  for (const match of cleanedContent.matchAll(PROPERTY_ID_RE)) {
    const propertyId = match[1];
    if (!propertyId) {
      continue;
    }
    references.push({
      key: `property:${propertyId}`,
      label: match[0].trim(),
      kind: "property",
      propertyId,
      note: `House ${propertyId}`,
    });
  }

  for (const match of cleanedContent.matchAll(HOUSE_LOCATOR_RE)) {
    const propertyId = match[1];
    if (!propertyId) {
      continue;
    }
    references.push({
      key: `property:${propertyId}`,
      label: match[0].trim(),
      kind: "property",
      propertyId,
      note: `House ${propertyId}`,
    });
  }

  for (const match of cleanedContent.matchAll(LISTING_KEY_RE)) {
    const listingKey = match[1];
    if (!listingKey) {
      continue;
    }
    references.push({
      key: `listing:${listingKey}`,
      label: match[0].trim(),
      kind: "listing",
      listingKey,
      note: listingKey,
    });
  }

  for (const match of cleanedContent.matchAll(LOCATOR_RE)) {
    const locator = match[1];
    if (!locator) {
      continue;
    }
    const reference = referenceFromLocator(locator, match[0].trim());
    if (reference) {
      references.push(reference);
    }
  }

  return dedupeReferences(references);
}
