#include <gst/gst.h>
#include <gst/sdp/sdp.h>
#include <gst/webrtc/webrtc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/time.h>
#include <unistd.h>

typedef enum { ROLE_NONE, ROLE_HOST, ROLE_CLIENT } SessionRole;

static void json_escape(FILE *out, const char *text) {
  fputc('"', out);
  for (const unsigned char *cursor = (const unsigned char *)text; *cursor; cursor++) {
    if (*cursor == '"' || *cursor == '\\') {
      fputc('\\', out);
      fputc(*cursor, out);
    } else if (*cursor == '\n') {
      fputs("\\n", out);
    } else if (*cursor == '\r') {
      fputs("\\r", out);
    } else {
      fputc(*cursor, out);
    }
  }
  fputc('"', out);
}

static void emit_json(const char *type, const char *sdp) {
  fputs("{\"type\":", stdout);
  json_escape(stdout, type);
  if (sdp) {
    fputs(",\"sdp\":", stdout);
    json_escape(stdout, sdp);
  }
  fputs("}\n", stdout);
  fflush(stdout);
}

static gchar *json_string_field(const char *json, const char *field) {
  gchar *needle = g_strdup_printf("\"%s\"", field);
  const char *key = strstr(json, needle);
  g_free(needle);
  if (!key)
    return NULL;
  const char *colon = strchr(key + strlen(field) + 2, ':');
  if (!colon)
    return NULL;
  const char *quote = strchr(colon, '"');
  if (!quote)
    return NULL;
  quote++;
  GString *value = g_string_new(NULL);
  for (const char *cursor = quote; *cursor && *cursor != '"'; cursor++) {
    if (*cursor == '\\' && cursor[1]) {
      cursor++;
      if (*cursor == 'n')
        g_string_append_c(value, '\n');
      else if (*cursor == 'r')
        g_string_append_c(value, '\r');
      else
        g_string_append_c(value, *cursor);
    } else {
      g_string_append_c(value, *cursor);
    }
  }
  return g_string_free(value, FALSE);
}

static gboolean wait_for_promise(GstPromise *promise, const gchar *step) {
  GstPromiseResult result = gst_promise_wait(promise);
  if (result != GST_PROMISE_RESULT_REPLIED) {
    g_printerr("%s failed: promise result %d\n", step, result);
    return FALSE;
  }
  return TRUE;
}

static gboolean set_description(GstElement *webrtc, const gchar *signal,
                                GstWebRTCSessionDescription *description) {
  GstPromise *promise = gst_promise_new();
  g_signal_emit_by_name(webrtc, signal, description, promise);
  gboolean ok = wait_for_promise(promise, signal);
  gst_promise_unref(promise);
  return ok;
}

static GstWebRTCSessionDescription *create_description(GstElement *webrtc,
                                                       const gchar *signal,
                                                       const gchar *field) {
  GstPromise *promise = gst_promise_new();
  g_signal_emit_by_name(webrtc, signal, NULL, promise);
  if (!wait_for_promise(promise, signal)) {
    gst_promise_unref(promise);
    return NULL;
  }
  const GstStructure *reply = gst_promise_get_reply(promise);
  GstWebRTCSessionDescription *description = NULL;
    if (!reply || !gst_structure_get(reply, field, GST_TYPE_WEBRTC_SESSION_DESCRIPTION,
                                   &description, NULL)) {
    g_printerr("%s returned no %s\n", signal, field);
  }
  gst_promise_unref(promise);
  return description;
}

static GstWebRTCSessionDescription *description_from_sdp(const char *sdp,
                                                         GstWebRTCSDPType type) {
  GstSDPMessage *message = NULL;
  if (gst_sdp_message_new(&message) != GST_SDP_OK)
    return NULL;
  if (gst_sdp_message_parse_buffer((const guint8 *)sdp, strlen(sdp), message) !=
      GST_SDP_OK) {
    gst_sdp_message_free(message);
    return NULL;
  }
  return gst_webrtc_session_description_new(type, message);
}

static void wait_ice_complete(GstElement *webrtc) {
  gint64 deadline = g_get_monotonic_time() + 5 * G_TIME_SPAN_SECOND;
  while (g_get_monotonic_time() < deadline) {
    GstWebRTCICEGatheringState state = GST_WEBRTC_ICE_GATHERING_STATE_NEW;
    g_object_get(webrtc, "ice-gathering-state", &state, NULL);
    if (state == GST_WEBRTC_ICE_GATHERING_STATE_COMPLETE)
      return;
    g_usleep(20000);
  }
}

static const char *pick_capture(void) {
  if (gst_element_factory_find("pipewiresrc"))
    return "pipewiresrc do-timestamp=true ! videoconvert ! queue";
  if (gst_element_factory_find("ximagesrc"))
    return "ximagesrc use-damage=false show-pointer=true ! videoconvert ! queue";
  return "videotestsrc is-live=true pattern=ball ! "
         "video/x-raw,width=1280,height=720,framerate=60/1 ! videoconvert ! queue";
}

static const char *pick_encoder(const char **codec) {
  if (gst_element_factory_find("nvh264enc") && gst_element_factory_find("rtph264pay")) {
    *codec = "h264";
    return "nvh264enc zerolatency=true ! h264parse config-interval=1 ! "
           "rtph264pay pt=96 config-interval=1 ! "
           "application/x-rtp,media=video,encoding-name=H264,payload=96";
  }
  if (gst_element_factory_find("vah264enc") && gst_element_factory_find("rtph264pay")) {
    *codec = "h264";
    return "vah264enc ! h264parse config-interval=1 ! "
           "rtph264pay pt=96 config-interval=1 ! "
           "application/x-rtp,media=video,encoding-name=H264,payload=96";
  }
  if (gst_element_factory_find("openh264enc") && gst_element_factory_find("rtph264pay")) {
    *codec = "h264";
    return "openh264enc ! h264parse config-interval=1 ! "
           "rtph264pay pt=96 config-interval=1 ! "
           "application/x-rtp,media=video,encoding-name=H264,payload=96";
  }
  *codec = "vp8";
  return "vp8enc deadline=1 cpu-used=8 keyframe-max-dist=60 ! "
         "rtpvp8pay pt=96 picture-id-mode=15-bit ! "
         "application/x-rtp,media=video,encoding-name=VP8,payload=96";
}

static void add_recv_transceiver(GstElement *client, const char *encoding,
                                 int payload) {
  gchar *caps_text = g_strdup_printf(
      "application/x-rtp,media=video,encoding-name=%s,payload=%d", encoding,
      payload);
  GstCaps *caps = gst_caps_from_string(caps_text);
  GstWebRTCRTPTransceiver *transceiver = NULL;
  g_signal_emit_by_name(client, "add-transceiver",
                        GST_WEBRTC_RTP_TRANSCEIVER_DIRECTION_RECVONLY, caps,
                        &transceiver);
  if (transceiver)
    gst_object_unref(transceiver);
  gst_caps_unref(caps);
  g_free(caps_text);
}

static GstElement *build_client(void) {
  GstElement *client = gst_element_factory_make("webrtcbin", "client");
  if (!client)
    return NULL;
  g_object_set(client, "bundle-policy", GST_WEBRTC_BUNDLE_POLICY_MAX_BUNDLE, NULL);
  add_recv_transceiver(client, "H264", 96);
  add_recv_transceiver(client, "VP8", 97);
  return client;
}

static GstElement *build_host_test(GError **error) {
  return gst_parse_launch(
      "webrtcbin name=host bundle-policy=max-bundle "
      "videotestsrc is-live=true pattern=ball ! "
      "video/x-raw,width=640,height=360,framerate=30/1 ! videoconvert ! queue ! "
      "vp8enc deadline=1 cpu-used=8 keyframe-max-dist=30 ! "
      "rtpvp8pay pt=96 picture-id-mode=15-bit ! "
      "application/x-rtp,media=video,encoding-name=VP8,payload=96 ! host.",
      error);
}

static GstElement *build_host_session(GError **error, const char **codec) {
  const char *capture = pick_capture();
  const char *encoder = pick_encoder(codec);
  gchar *pipeline = g_strdup_printf(
      "webrtcbin name=host bundle-policy=max-bundle "
      "%s ! %s ! host.",
      capture, encoder);
  GstElement *element = gst_parse_launch(pipeline, error);
  g_free(pipeline);
  return element;
}

static void on_decode_pad(GstElement *decodebin, GstPad *pad, gpointer sink) {
  if (GST_PAD_DIRECTION(pad) != GST_PAD_SRC)
    return;
  GstPad *sinkpad = gst_element_get_static_pad(GST_ELEMENT(sink), "sink");
  if (sinkpad && !gst_pad_is_linked(sinkpad))
    gst_pad_link(pad, sinkpad);
  if (sinkpad)
    gst_object_unref(sinkpad);
  (void)decodebin;
}

static void on_webrtc_pad(GstElement *webrtc, GstPad *pad, gpointer pipeline) {
  if (GST_PAD_DIRECTION(pad) != GST_PAD_SRC)
    return;
  GstElement *decode = gst_element_factory_make("decodebin", NULL);
  GstElement *convert = gst_element_factory_make("videoconvert", NULL);
  GstElement *sink = gst_element_factory_make("autovideosink", NULL);
  if (!decode || !convert || !sink)
    return;
  g_object_set(sink, "sync", FALSE, NULL);
  gst_bin_add_many(GST_BIN(pipeline), decode, convert, sink, NULL);
  gst_element_link(convert, sink);
  g_signal_connect(decode, "pad-added", G_CALLBACK(on_decode_pad), convert);
  gst_element_sync_state_with_parent(decode);
  gst_element_sync_state_with_parent(convert);
  gst_element_sync_state_with_parent(sink);
  GstPad *sinkpad = gst_element_get_static_pad(decode, "sink");
  gst_pad_link(pad, sinkpad);
  gst_object_unref(sinkpad);
  (void)webrtc;
}

static int emit_local_sdp(GstElement *webrtc, const char *type,
                          GstWebRTCSessionDescription *description) {
  if (!description || !set_description(webrtc, "set-local-description", description))
    return 1;
  wait_ice_complete(webrtc);
  gchar *text = gst_sdp_message_as_text(description->sdp);
  emit_json(type, text);
  g_free(text);
  return 0;
}

static int apply_remote_sdp(GstElement *webrtc, const char *sdp, GstWebRTCSDPType type) {
  GstWebRTCSessionDescription *description = description_from_sdp(sdp, type);
  if (!description) {
    emit_json("error", "invalid remote sdp");
    return 1;
  }
  gboolean ok = set_description(webrtc, "set-remote-description", description);
  gst_webrtc_session_description_free(description);
  return ok ? 0 : 1;
}

static char *read_line(void) {
  GString *buffer = g_string_new(NULL);
  int next;
  while ((next = fgetc(stdin)) != EOF) {
    g_string_append_c(buffer, (gchar)next);
    if (next == '\n')
      return g_string_free(buffer, FALSE);
  }
  if (buffer->len == 0) {
    g_string_free(buffer, TRUE);
    return NULL;
  }
  return g_string_free(buffer, FALSE);
}

static int run_session(SessionRole role) {
  GError *error = NULL;
  const char *codec = "vp8";
  GstElement *pipeline = NULL;
  GstElement *webrtc = NULL;
  if (role == ROLE_HOST) {
    pipeline = build_host_session(&error, &codec);
    webrtc = pipeline ? gst_bin_get_by_name(GST_BIN(pipeline), "host") : NULL;
  } else {
    webrtc = build_client();
    pipeline = gst_pipeline_new("kabin-client");
    if (webrtc && pipeline) {
      gst_bin_add(GST_BIN(pipeline), webrtc);
      g_signal_connect(webrtc, "pad-added", G_CALLBACK(on_webrtc_pad), pipeline);
    }
  }
  if (!pipeline || !webrtc) {
    emit_json("error", error ? error->message : "failed to build stream pipeline");
    g_clear_error(&error);
    if (webrtc && role == ROLE_HOST)
      gst_object_unref(webrtc);
    if (pipeline)
      gst_object_unref(pipeline);
    return 1;
  }

  gst_element_set_state(pipeline, GST_STATE_PLAYING);
  emit_json("hello", role == ROLE_HOST ? "host" : "client");

  if (role == ROLE_CLIENT) {
    GstWebRTCSessionDescription *offer =
        create_description(webrtc, "create-offer", "offer");
    if (emit_local_sdp(webrtc, "offer", offer) != 0) {
      if (offer)
        gst_webrtc_session_description_free(offer);
      gst_element_set_state(pipeline, GST_STATE_NULL);
      gst_object_unref(webrtc);
      gst_object_unref(pipeline);
      return 1;
    }
    if (offer)
      gst_webrtc_session_description_free(offer);
  }

  while (TRUE) {
    char *line = read_line();
    if (!line)
      break;
    gchar *type = json_string_field(line, "type");
    gchar *sdp = json_string_field(line, "sdp");
    int rc = 0;
    if (type && strcmp(type, "offer") == 0 && role == ROLE_HOST && sdp) {
      rc = apply_remote_sdp(webrtc, sdp, GST_WEBRTC_SDP_TYPE_OFFER);
      if (rc == 0) {
        GstWebRTCSessionDescription *answer =
            create_description(webrtc, "create-answer", "answer");
        rc = emit_local_sdp(webrtc, "answer", answer);
        if (answer)
          gst_webrtc_session_description_free(answer);
      }
    } else if (type && strcmp(type, "answer") == 0 && role == ROLE_CLIENT && sdp) {
      rc = apply_remote_sdp(webrtc, sdp, GST_WEBRTC_SDP_TYPE_ANSWER);
      if (rc == 0)
        emit_json("ready", codec);
    } else if (type && strcmp(type, "close") == 0) {
      g_free(type);
      g_free(sdp);
      g_free(line);
      break;
    }
    g_free(type);
    g_free(sdp);
    g_free(line);
    if (rc != 0)
      break;
  }

  gst_element_set_state(pipeline, GST_STATE_NULL);
  if (role == ROLE_HOST)
    gst_object_unref(webrtc);
  gst_object_unref(pipeline);
  return 0;
}

static int self_test(void) {
  GError *error = NULL;
  GstElement *client = build_client();
  GstElement *host_pipeline = build_host_test(&error);
  if (!client || !host_pipeline) {
    g_printerr("pipeline creation failed: %s\n",
               error ? error->message : "missing WebRTC element");
    g_clear_error(&error);
    if (client)
      gst_object_unref(client);
    if (host_pipeline)
      gst_object_unref(host_pipeline);
    return 1;
  }
  GstElement *host = gst_bin_get_by_name(GST_BIN(host_pipeline), "host");
  gst_element_set_state(client, GST_STATE_PLAYING);
  gst_element_set_state(host_pipeline, GST_STATE_PLAYING);

  GstWebRTCSessionDescription *offer =
      create_description(client, "create-offer", "offer");
  GstWebRTCSessionDescription *answer = NULL;
  gboolean ok = offer && set_description(client, "set-local-description", offer) &&
                set_description(host, "set-remote-description", offer);
  if (ok)
    answer = create_description(host, "create-answer", "answer");
  ok = ok && answer && set_description(host, "set-local-description", answer) &&
       set_description(client, "set-remote-description", answer);

  if (offer)
    gst_webrtc_session_description_free(offer);
  if (answer)
    gst_webrtc_session_description_free(answer);
  gst_element_set_state(client, GST_STATE_NULL);
  gst_element_set_state(host_pipeline, GST_STATE_NULL);
  gst_object_unref(host);
  gst_object_unref(client);
  gst_object_unref(host_pipeline);

  if (!ok)
    return 1;
  puts("{\"ok\":true,\"transport\":\"webrtc\",\"codec\":\"vp8\"}");
  return 0;
}

static void on_play_source_setup(GstElement *playbin, GstElement *source,
                                 gpointer authorization) {
  (void)playbin;
  if (!authorization || !GST_IS_OBJECT(source))
    return;
  if (!g_object_class_find_property(G_OBJECT_GET_CLASS(source), "extra-headers"))
    return;
  GstStructure *headers = gst_structure_new(
      "extra-headers", "Authorization", G_TYPE_STRING, (const gchar *)authorization,
      NULL);
  g_object_set(source, "extra-headers", headers, NULL);
  gst_structure_free(headers);
}

static gboolean emit_play_position(GstElement *playbin) {
  gint64 position = 0;
  gint64 duration = 0;
  if (!gst_element_query_position(playbin, GST_FORMAT_TIME, &position))
    return TRUE;
  gst_element_query_duration(playbin, GST_FORMAT_TIME, &duration);
  gchar *payload = g_strdup_printf("%.3f %.3f", position / (double)GST_SECOND,
                                   duration > 0 ? duration / (double)GST_SECOND : 0);
  emit_json("position", payload);
  g_free(payload);
  return TRUE;
}

static int run_play(const char *uri, double start_seconds, const char *authorization) {
  GstElement *playbin = gst_element_factory_make("playbin", "play");
  if (!playbin) {
    emit_json("error", "playbin is not available");
    return 1;
  }
  g_object_set(playbin, "uri", uri, NULL);
  if (authorization && authorization[0])
    g_signal_connect(playbin, "source-setup", G_CALLBACK(on_play_source_setup),
                     (gpointer)authorization);

  gst_element_set_state(playbin, GST_STATE_PLAYING);
  if (gst_element_get_state(playbin, NULL, NULL, 5 * GST_SECOND) ==
      GST_STATE_CHANGE_FAILURE) {
    emit_json("error", "could not start playback");
    gst_object_unref(playbin);
    return 1;
  }
  if (start_seconds > 0.5) {
    gst_element_seek_simple(playbin, GST_FORMAT_TIME,
                            (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
                            (gint64)(start_seconds * GST_SECOND));
  }
  emit_json("hello", "play");
  emit_json("ready", uri);

  GstBus *bus = gst_element_get_bus(playbin);
  int rc = 0;
  while (TRUE) {
    GstMessage *message =
        gst_bus_timed_pop_filtered(bus, 200 * GST_MSECOND,
                                   (GstMessageType)(GST_MESSAGE_EOS | GST_MESSAGE_ERROR));
    if (message) {
      if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR) {
        emit_json("error", "playback failed");
        rc = 1;
      } else {
        emit_json("eos", "done");
      }
      gst_message_unref(message);
      break;
    }
    emit_play_position(playbin);
    if (feof(stdin))
      break;
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(fileno(stdin), &readfds);
    struct timeval timeout = {0, 0};
    if (select(fileno(stdin) + 1, &readfds, NULL, NULL, &timeout) > 0) {
      char *line = read_line();
      if (!line)
        break;
      gchar *type = json_string_field(line, "type");
      gchar *sdp = json_string_field(line, "sdp");
      if (type && strcmp(type, "close") == 0) {
        g_free(type);
        g_free(sdp);
        g_free(line);
        break;
      }
      if (type && strcmp(type, "seek") == 0 && sdp) {
        gst_element_seek_simple(
            playbin, GST_FORMAT_TIME,
            (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
            (gint64)(g_ascii_strtod(sdp, NULL) * GST_SECOND));
      }
      if (type && strcmp(type, "pause") == 0)
        gst_element_set_state(playbin, GST_STATE_PAUSED);
      if (type && strcmp(type, "resume") == 0)
        gst_element_set_state(playbin, GST_STATE_PLAYING);
      if (type && strcmp(type, "volume") == 0 && sdp)
        g_object_set(playbin, "volume", g_ascii_strtod(sdp, NULL), NULL);
      g_free(type);
      g_free(sdp);
      g_free(line);
    }
  }
  emit_play_position(playbin);
  gst_object_unref(bus);
  gst_element_set_state(playbin, GST_STATE_NULL);
  gst_object_unref(playbin);
  return rc;
}

int main(int argc, char **argv) {
  gst_init(&argc, &argv);
  if (argc == 2 && strcmp(argv[1], "--self-test") == 0)
    return self_test();
  if (argc == 3 && strcmp(argv[1], "--session") == 0) {
    if (strcmp(argv[2], "host") == 0)
      return run_session(ROLE_HOST);
    if (strcmp(argv[2], "client") == 0)
      return run_session(ROLE_CLIENT);
  }
  if (argc >= 3 && strcmp(argv[1], "--play") == 0) {
    double start = 0;
    const char *authorization = g_getenv("KABIN_MEDIA_AUTH");
    for (int index = 3; index + 1 < argc; index += 2) {
      if (strcmp(argv[index], "--start") == 0)
        start = g_ascii_strtod(argv[index + 1], NULL);
    }
    return run_play(argv[2], start, authorization);
  }
  g_printerr(
      "usage: kabin-media-helper --self-test | --session host|client | --play URI [--start seconds]\n");
  return 2;
}
