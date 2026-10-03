/**
 * DEV-ONLY sample data. Never shipped: the production build drops src/mocks
 * and scripts/check-dist.mjs fails if any of it leaks.
 *
 * What is real here: problem texts, correct outputs and predicted outputs are
 * copied from data/problems.jsonl; belief descriptions from
 * data/misconceptions.jsonl; traces were recorded by running each program
 * under sys.settrace. What is invented: every score, the explanations, the
 * evaluation numbers. The UI shows a SAMPLE DATA banner whenever these load.
 */

export const LIBRARY = {
  RANGE_FROM_1: { description: "Believes range(n) counts from 1 to n.", topic: "loops", confusable_group: "RANGE_BOUNDS" },
  RANGE_INCLUDES_END: {
    description: "Believes range(n) counts from 0 up to and including n.",
    topic: "loops",
    confusable_group: "RANGE_BOUNDS",
  },
  RESET_STATE_EACH_ITERATION: {
    description:
      "Believes each pass through a loop starts again from the values the variables had before the loop, so updates do not carry over.",
    topic: "loops",
    confusable_group: "LOOP_ACCUMULATION",
  },
  LOOP_BODY_RUNS_ONCE_LAST: {
    description: "Believes a for loop runs its body only once, using the last value in the sequence.",
    topic: "loops",
    confusable_group: "LOOP_ACCUMULATION",
  },
  AFTER_LOOP_IS_REPEATED: {
    description:
      "Believes a statement placed right after a loop, without indentation, is also repeated on every pass of the loop.",
    topic: "loops",
    confusable_group: "LOOP_BODY_SCOPE",
  },
  SLIP: {
    description: "Made a careless slip such as a typo or an arithmetic error while understanding the concept correctly.",
    topic: null,
    confusable_group: null,
  },
  STRING_DIGITS_ADD_NUMERIC: {
    description: "Believes + on two strings made of digits adds them as numbers instead of joining them.",
    topic: "strings",
    confusable_group: "STRING_NUMBER",
  },
  CONCAT_ADDS_SPACE: {
    description: "Believes joining strings with + automatically puts a space between them.",
    topic: "strings",
    confusable_group: "OUTPUT_SPACING",
  },
}

export const PROBLEMS = {
  PO_LOOP_01: {
    problem_id: "PO_LOOP_01",
    item_type: "predict_output",
    topic: "loops",
    problem_text: "total = 0\nfor i in range(4):\n    total = total + i\nprint(total)",
    correct_output: "6",
    predicted_outputs: {
      RANGE_FROM_1: "10",
      RANGE_INCLUDES_END: "10",
      RESET_STATE_EACH_ITERATION: "3",
      LOOP_BODY_RUNS_ONCE_LAST: "3",
      AFTER_LOOP_IS_REPEATED: "0\n1\n3\n6",
    },
  },
  PO_LOOP_02: {
    problem_id: "PO_LOOP_02",
    item_type: "predict_output",
    topic: "loops",
    problem_text: 'for i in range(3):\n    print("row", i)\n    print("-")\nprint("end")',
    correct_output: "row 0\n-\nrow 1\n-\nrow 2\n-\nend",
    predicted_outputs: {
      RANGE_FROM_1: "row 1\n-\nrow 2\n-\nrow 3\n-\nend",
      RANGE_INCLUDES_END: "row 0\n-\nrow 1\n-\nrow 2\n-\nrow 3\n-\nend",
    },
  },
  PO_LIST_22: {
    problem_id: "PO_LIST_22",
    item_type: "predict_output",
    topic: "lists",
    problem_text: 'colors = ["red", "blue"]\nfor i in range(len(colors)):\n    print(i)\nprint(len(colors))',
    correct_output: "0\n1\n2",
    predicted_outputs: { RANGE_LEN_GIVES_ITEMS: "red\nblue\n2", RANGE_FROM_1: "1\n2\n2" },
  },
  PO_LOOP_04: {
    problem_id: "PO_LOOP_04",
    item_type: "predict_output",
    topic: "loops",
    problem_text: "for i in range(3):\n    print(i)\nfor j in range(1, 3):\n    print(j)",
    correct_output: "0\n1\n2\n1\n2",
    predicted_outputs: {
      RANGE_FROM_1: "1\n2\n3\n1\n2",
      RANGE_SECOND_ARG_IS_COUNT: "0\n1\n2\n1\n2\n3",
      RANGE_INCLUDES_END: "0\n1\n2\n3\n1\n2\n3",
    },
  },
  PO_STR_05: {
    problem_id: "PO_STR_05",
    item_type: "predict_output",
    topic: "strings",
    problem_text: 'a = "3"\nb = a * 2\nc = a + "1"\nprint(b)\nprint(c)',
    correct_output: "33\n31",
    predicted_outputs: { STRING_DIGITS_MULTIPLY_NUMERIC: "6\n31", STRING_DIGITS_ADD_NUMERIC: "33\n4" },
  },
  PO_STR_04: {
    problem_id: "PO_STR_04",
    item_type: "predict_output",
    topic: "strings",
    problem_text: 'x = "4"\ny = "5"\nz = x + y\nprint(z)\nprint(z + "!")',
    correct_output: "45\n45!",
    predicted_outputs: { STRING_DIGITS_ADD_NUMERIC: "9\n9!", CONCAT_ADDS_SPACE: "4 5\n4 5 !" },
  },
  PO_STR_13: {
    problem_id: "PO_STR_13",
    item_type: "predict_output",
    topic: "strings",
    problem_text: 'a = "12"\nb = "3"\nprint(a + b)\nprint(a, b)',
    correct_output: "123\n12 3",
    predicted_outputs: { STRING_DIGITS_ADD_NUMERIC: "15\n12 3", PRINT_COMMA_NO_SPACE: "123\n123" },
  },
}

/** Recorded with sys.settrace: line about to run, locals at that moment, stdout so far. */
export const TRACES = {
  PO_LOOP_01: [
    { line: 1, locals: {}, stdout: "" },
    { line: 2, locals: { total: "0" }, stdout: "" },
    { line: 3, locals: { total: "0", i: "0" }, stdout: "" },
    { line: 2, locals: { total: "0", i: "0" }, stdout: "" },
    { line: 3, locals: { total: "0", i: "1" }, stdout: "" },
    { line: 2, locals: { total: "1", i: "1" }, stdout: "" },
    { line: 3, locals: { total: "1", i: "2" }, stdout: "" },
    { line: 2, locals: { total: "3", i: "2" }, stdout: "" },
    { line: 3, locals: { total: "3", i: "3" }, stdout: "" },
    { line: 2, locals: { total: "6", i: "3" }, stdout: "" },
    { line: 4, locals: { total: "6", i: "3" }, stdout: "" },
    { line: 4, locals: { total: "6", i: "3" }, stdout: "6", end: true },
  ],
  PO_STR_05: [
    { line: 1, locals: {}, stdout: "" },
    { line: 2, locals: { a: "'3'" }, stdout: "" },
    { line: 3, locals: { a: "'3'", b: "'33'" }, stdout: "" },
    { line: 4, locals: { a: "'3'", b: "'33'", c: "'31'" }, stdout: "" },
    { line: 5, locals: { a: "'3'", b: "'33'", c: "'31'" }, stdout: "33" },
    { line: 5, locals: { a: "'3'", b: "'33'", c: "'31'" }, stdout: "33\n31", end: true },
  ],
}

/** Teaching per belief: hand-written for the sample, with the divergence line. */
export const TEACHING = {
  RANGE_FROM_1: {
    line: 2,
    note: "You expected i to start at 1. range(4) gives 0, 1, 2, 3.",
    text:
      "range(4) produces four numbers, but it starts counting at 0, not 1: the values are 0, 1, 2 and 3.\n\n" +
      "So the loop adds 0 + 1 + 2 + 3, which is 6. Counting from 1 to 4 would give 10, which is the answer you wrote.",
  },
  RANGE_INCLUDES_END: {
    line: 2,
    note: "range(4) stops before 4, so i is never 4.",
    text:
      "range(4) starts at 0 and stops just before 4. The stop value is never produced.\n\n" +
      "The loop adds 0 + 1 + 2 + 3 = 6. Including 4 would give 10, which is the answer you wrote.",
  },
  RESET_STATE_EACH_ITERATION: {
    line: 3,
    note: "total keeps its new value on the next pass.",
    text:
      "Each pass of the loop sees the value total was left with by the previous pass. Nothing resets it.\n\n" +
      "So total grows 0, 0, 1, 3 and finishes at 6.",
  },
  LOOP_BODY_RUNS_ONCE_LAST: {
    line: 3,
    note: "This line runs four times, once for each value of i.",
    text: "The indented body runs once for every value range(4) produces, not just the last one. Step through and count the passes.",
  },
  AFTER_LOOP_IS_REPEATED: {
    line: 4,
    note: "print is not indented, so it runs once, after the loop ends.",
    text: "Only indented lines belong to the loop. print(total) sits at the left margin, so it runs once, when the loop has finished.",
  },
  STRING_DIGITS_ADD_NUMERIC: {
    line: 3,
    note: '"3" + "1" joins the text: "31", not 4.',
    text:
      'a holds the text "3", not the number 3. With two strings, + joins them end to end.\n\n' +
      'So a + "1" is "31". Python only adds numerically when both sides are numbers.',
  },
}

/** Which unseen problems retest each belief. */
export const RETEST = {
  loops: [
    { id: "PO_LIST_22", transfer: "different_topic" },
    { id: "PO_LOOP_04", transfer: null },
  ],
  strings: [
    { id: "PO_STR_04", transfer: null },
    { id: "PO_STR_13", transfer: null },
  ],
}

/** The two cases a sample session walks through, with invented scores. */
export const CASES = [
  {
    problem: "PO_LOOP_01",
    traceOf: "PO_LOOP_01",
    retest: "loops",
    byAnswer: {
      "10": {
        candidates: [
          ["RANGE_FROM_1", 0.71],
          ["RANGE_INCLUDES_END", 0.68],
          ["AFTER_LOOP_IS_REPEATED", 0.29],
        ],
        probe: { problem: "PO_LOOP_02", pair: ["RANGE_FROM_1", "RANGE_INCLUDES_END"] },
      },
      "3": {
        candidates: [
          ["RESET_STATE_EACH_ITERATION", 0.74],
          ["LOOP_BODY_RUNS_ONCE_LAST", 0.52],
          ["RANGE_FROM_1", 0.31],
        ],
      },
      "0\n1\n3\n6": {
        candidates: [
          ["AFTER_LOOP_IS_REPEATED", 0.77],
          ["RESET_STATE_EACH_ITERATION", 0.33],
          ["SLIP", 0.21],
        ],
      },
    },
    otherwise: {
      candidates: [
        ["SLIP", 0.41],
        ["RANGE_FROM_1", 0.33],
        ["RANGE_INCLUDES_END", 0.3],
      ],
      draft: null,
    },
  },
  {
    problem: "PO_STR_05",
    traceOf: "PO_STR_05",
    retest: "strings",
    byAnswer: {
      "33\n4": {
        candidates: [
          ["STRING_DIGITS_ADD_NUMERIC", 0.79],
          ["CONCAT_ADDS_SPACE", 0.38],
          ["SLIP", 0.27],
        ],
      },
      // STRING_DIGITS_MULTIPLY_NUMERIC is held out of the library, so this
      // answer has no match: the unknown path, with a drafted belief.
      "6\n31": {
        candidates: [
          ["STRING_DIGITS_ADD_NUMERIC", 0.44],
          ["SLIP", 0.36],
          ["CONCAT_ADDS_SPACE", 0.22],
        ],
        unknown: true,
        draft: "Believes multiplying a string of digits by a whole number multiplies the number instead of repeating the text.",
      },
    },
    otherwise: {
      candidates: [
        ["SLIP", 0.39],
        ["STRING_DIGITS_ADD_NUMERIC", 0.35],
        ["CONCAT_ADDS_SPACE", 0.24],
      ],
      draft: null,
    },
  },
]

export const TOPICS = [
  { topic: "variables", problem_count: 14 },
  { topic: "conditionals", problem_count: 19 },
  { topic: "loops", problem_count: 25 },
  { topic: "functions", problem_count: 23 },
  { topic: "lists", problem_count: 30 },
  { topic: "strings", problem_count: 24 },
]

/** Invented numbers in the shape ml/evaluate.py writes, to build the page against. */
export const EVALUATION = {
  source: "SAMPLE DATA (dev fixture, not results/)",
  generated_at: null,
  runs: {
    untuned: {
      model: "google/embeddinggemma-300m",
      tag: "untuned",
      seen_misconceptions_new_problems: { n: 374, top1: 0.312, top3: 0.548 },
      held_out_misconceptions_descriptions_added: { n: 150, top1: 0.287, top3: 0.513 },
    },
    finetuned: {
      model: "models/relearn-embeddinggemma",
      tag: "finetuned",
      thresholds: { unknown_below: 0.4812, unknown_val_balanced_acc: 0.741, probe_gap: 0.08 },
      seen_misconceptions_new_problems: { n: 374, top1: 0.684, top3: 0.887 },
      held_out_misconceptions_descriptions_added: { n: 150, top1: 0.453, top3: 0.72 },
      unknown_detection: { held_out_flagged_unknown: 0.62, seen_wrongly_flagged_unknown: 0.14 },
      within_confusable_groups: {
        n: 301,
        without_probe: 0.71,
        with_simulated_probe: 0.86,
        note: "probe simulated with bank problems whose predicted outputs differ; assumes a consistent student",
      },
      ablation_no_reason: { seen: { n: 374, top1: 0.52, top3: 0.79 }, held_out: { n: 150, top1: 0.31, top3: 0.58 } },
      baseline_lookup_table: { n: 524, covered: 38, top1: 0.061 },
    },
  },
}
