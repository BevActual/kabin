// Exercises json_string_field()'s escape handling directly, without
// spinning up GStreamer/WebRTC. Built and run by scripts/test-media-helper.sh.
#define main kabin_media_helper_original_main
#include "kabin-media-helper.c"
#undef main

static int failures = 0;

static void check_str(const char *label, const char *got, const char *expected) {
  if (got == NULL || strcmp(got, expected) != 0) {
    fprintf(stderr, "FAIL %s: got=%s expected=%s\n", label, got ? got : "(null)", expected);
    failures++;
  } else {
    printf("ok %s\n", label);
  }
}

int main(void) {
  gchar *v;

  // \t and \" - previously \t became a literal 't', losing the tab.
  v = json_string_field(
      "{\"type\":\"offer\",\"sdp\":\"tab\\there, quote\\\"here\"}", "sdp");
  check_str("tab and quote escapes", v, "tab\there, quote\"here");
  g_free(v);

  // \uXXXX BMP codepoint (e-acute) - previously became literal "u00e9".
  // Python's json.dumps() (ensure_ascii=True, the default) emits this for
  // any non-ASCII character reaching the helper's stdin.
  v = json_string_field("{\"sdp\":\"unicode\\u00e9end\"}", "sdp");
  check_str("BMP \\u escape", v, "unicode\xc3\xa9""end");
  g_free(v);

  // Surrogate pair (grinning face emoji, U+1F600) - previously became
  // literal "uD83DuDE00" split across two collapsed 'u' chars.
  v = json_string_field("{\"sdp\":\"emoji\\ud83d\\ude00end\"}", "sdp");
  check_str("surrogate pair \\u escape", v, "emoji\xf0\x9f\x98\x80""end");
  g_free(v);

  // \/ and \\ - already worked before, must still work.
  v = json_string_field("{\"sdp\":\"a\\/b\\\\c\"}", "sdp");
  check_str("solidus and backslash escapes", v, "a/b\\c");
  g_free(v);

  // Malformed \u (not 4 hex digits) must not crash - falls back to a
  // literal 'u' and keeps scanning from the next character.
  v = json_string_field("{\"sdp\":\"bad\\uZZZZend\"}", "sdp");
  if (v == NULL) {
    fprintf(stderr, "FAIL malformed \\u: returned NULL (crashed or errored)\n");
    failures++;
  } else {
    printf("ok malformed \\u did not crash, got: %s\n", v);
  }
  g_free(v);

  // A high surrogate with nothing following it must not crash either.
  v = json_string_field("{\"sdp\":\"lone\\ud83dend\"}", "sdp");
  if (v == NULL) {
    fprintf(stderr, "FAIL lone high surrogate: returned NULL (crashed or errored)\n");
    failures++;
  } else {
    printf("ok lone high surrogate did not crash, got %zu bytes\n", strlen(v));
  }
  g_free(v);

  if (failures) {
    fprintf(stderr, "%d check(s) failed\n", failures);
    return 1;
  }
  printf("ALL OK\n");
  return 0;
}
