#include <gst/gst.h>
#include <gst/sdp/sdp.h>
#include <gst/webrtc/webrtc.h>
#include <stdio.h>
#include <string.h>

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
  if (!reply || !gst_structure_get(reply, field,
                                   GST_TYPE_WEBRTC_SESSION_DESCRIPTION,
                                   &description, NULL)) {
    g_printerr("%s returned no %s\n", signal, field);
  }
  gst_promise_unref(promise);
  return description;
}

static GstElement *build_client(void) {
  GstElement *client = gst_element_factory_make("webrtcbin", "client");
  if (!client)
    return NULL;
  g_object_set(client, "bundle-policy", GST_WEBRTC_BUNDLE_POLICY_MAX_BUNDLE,
               NULL);
  GstCaps *caps = gst_caps_from_string(
      "application/x-rtp,media=video,encoding-name=VP8,payload=96");
  GstWebRTCRTPTransceiver *transceiver = NULL;
  g_signal_emit_by_name(client, "add-transceiver",
                        GST_WEBRTC_RTP_TRANSCEIVER_DIRECTION_RECVONLY, caps,
                        &transceiver);
  if (transceiver)
    gst_object_unref(transceiver);
  gst_caps_unref(caps);
  return client;
}

static GstElement *build_host(GError **error) {
  return gst_parse_launch(
      "webrtcbin name=host bundle-policy=max-bundle "
      "videotestsrc is-live=true pattern=ball ! "
      "video/x-raw,width=640,height=360,framerate=30/1 ! videoconvert ! queue ! "
      "vp8enc deadline=1 cpu-used=8 keyframe-max-dist=30 ! "
      "rtpvp8pay pt=96 picture-id-mode=15-bit ! "
      "application/x-rtp,media=video,encoding-name=VP8,payload=96 ! host.",
      error);
}

static int self_test(void) {
  GError *error = NULL;
  GstElement *client = build_client();
  GstElement *host_pipeline = build_host(&error);
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

int main(int argc, char **argv) {
  gst_init(&argc, &argv);
  if (argc == 2 && strcmp(argv[1], "--self-test") == 0)
    return self_test();
  g_printerr("usage: kabin-media-helper --self-test\n");
  return 2;
}
