import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const APP_NAME_STOP_WORDS = new Set([
  "a",
  "an",
  "and",
  "app",
  "application",
  "build",
  "create",
  "for",
  "make",
  "me",
  "modern",
  "new",
  "page",
  "responsive",
  "site",
  "the",
  "to",
  "website",
  "with",
]);

export function deriveAppNameFromPrompt(prompt: string): string {
  const cleanPrompt = prompt.trim();
  if (!cleanPrompt) return "Vini Canvas App";

  const titleCaseName = (value: string): string => {
    const minorWords = new Set([
      "a",
      "an",
      "and",
      "at",
      "by",
      "for",
      "in",
      "of",
      "on",
      "the",
      "to",
      "with",
    ]);
    return value
      .replace(/[^A-Za-z0-9\s&'-]/g, " ")
      .split(/\s+/)
      .map((word) => word.trim())
      .filter(Boolean)
      .slice(0, 6)
      .map((word, index) => {
        const lower = word.toLowerCase();
        if (index > 0 && minorWords.has(lower)) return lower;
        return lower.charAt(0).toUpperCase() + lower.slice(1);
      })
      .join(" ")
      .trim();
  };

  const namedMatch = cleanPrompt.match(
    /\b(?:called|named)\s+["']?(.{2,90}?)(?:["']?(?:[.!?,;:\n]|$))/i,
  );
  if (namedMatch?.[1]) {
    const candidate = namedMatch[1]
      .trim()
      .replace(/\b(?:build|create|include|make|use|with)\b.*$/i, "")
      .trim()
      .replace(/^["']|["']$/g, "");
    const name = titleCaseName(candidate);
    if (name) return name.slice(0, 60);
  }

  const words = cleanPrompt
    .replace(/[^A-Za-z0-9\s-]/g, " ")
    .split(/\s+/)
    .map((word) => word.trim())
    .filter((word) => {
      if (!word) return false;
      return !APP_NAME_STOP_WORDS.has(word.toLowerCase());
    })
    .slice(0, 5);

  const name = titleCaseName(words.join(" "));
  return (name || "Vini Canvas App").slice(0, 60);
}

/**
 * Generates a cute app name.
 */
export function generateCuteAppName(): string {
  const adjectives = [
    "happy",
    "gentle",
    "brave",
    "clever",
    "swift",
    "bright",
    "calm",
    "nimble",
    "sleepy",
    "fluffy",
    "wild",
    "tiny",
    "bold",
    "wise",
    "merry",
    "quick",
    "busy",
    "silent",
    "cozy",
    "jolly",
    "playful",
    "friendly",
    "curious",
    "peaceful",
    "silly",
    "dazzling",
    "graceful",
    "elegant",
    "cosmic",
    "whispering",
    "dancing",
    "sparkling",
    "mystical",
    "vibrant",
    "radiant",
    "dreamy",
    "patient",
    "energetic",
    "vigilant",
    "sincere",
    "electric",
    "stellar",
    "lunar",
    "serene",
    "mighty",
    "magical",
    "neon",
    "azure",
    "crimson",
    "emerald",
    "golden",
    "jade",
    "crystal",
    "snuggly",
    "glowing",
    "wandering",
    "whistling",
    "bubbling",
    "floating",
    "flying",
    "hopping",
  ];

  const animals = [
    "fox",
    "panda",
    "rabbit",
    "wolf",
    "bear",
    "owl",
    "koala",
    "beaver",
    "ferret",
    "squirrel",
    "zebra",
    "tiger",
    "lynx",
    "lemur",
    "penguin",
    "otter",
    "hedgehog",
    "deer",
    "badger",
    "raccoon",
    "turtle",
    "dolphin",
    "eagle",
    "falcon",
    "parrot",
    "capybara",
    "axolotl",
    "narwhal",
    "wombat",
    "meerkat",
    "platypus",
    "mongoose",
    "chinchilla",
    "quokka",
    "alpaca",
    "chameleon",
    "ocelot",
    "manatee",
    "puffin",
    "shiba",
    "sloth",
    "gecko",
    "hummingbird",
    "mantis",
    "jellyfish",
    "pangolin",
    "okapi",
    "binturong",
    "tardigrade",
    "beluga",
    "kiwi",
    "octopus",
    "salamander",
    "seahorse",
    "kookaburra",
    "gibbon",
    "jackrabbit",
    "lobster",
    "iguana",
    "tamarin",
    "armadillo",
    "starfish",
    "walrus",
    "phoenix",
    "griffin",
    "dragon",
    "unicorn",
    "kraken",
  ];

  const verbs = [
    "run",
    "hop",
    "dash",
    "zoom",
    "skip",
    "jump",
    "glow",
    "play",
    "chirp",
    "buzz",
    "flip",
    "flit",
    "soar",
    "dive",
    "swim",
    "climb",
    "sprint",
    "wiggle",
    "twirl",
    "pounce",
    "bop",
    "spin",
    "hum",
    "roll",
    "blink",
    "skid",
    "kick",
    "drift",
    "bloom",
    "burst",
    "slide",
    "bounce",
    "crawl",
    "sniff",
    "peek",
    "scurry",
    "nudge",
    "snap",
    "swoop",
    "roam",
    "trot",
    "dart",
    "yawn",
    "snore",
    "hug",
    "nap",
    "chase",
    "rest",
    "wag",
    "bob",
    "beam",
    "cheer",
  ];

  const randomAdjective =
    adjectives[Math.floor(Math.random() * adjectives.length)];
  const randomAnimal = animals[Math.floor(Math.random() * animals.length)];
  const randomVerb = verbs[Math.floor(Math.random() * verbs.length)];
  return `${randomAdjective}-${randomAnimal}-${randomVerb}`;
}
