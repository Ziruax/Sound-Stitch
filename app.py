import streamlit as st
import tempfile
import os
import numpy as np
from PIL import Image
from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

# ----------------------------------------------------------------------
# Streamlit page configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Audio + Images → Video",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬  Combine Audio & Images into Video (Ken Burns Effect)")
st.markdown(
    """
    Upload an **audio file** and several **images**.  
    The audio will be split equally across all images, and each image will be shown with a subtle zoom‑in effect (Ken Burns).  
    Choose the order of the images, then click **Generate Video**.
    """
)

# ----------------------------------------------------------------------
# File uploaders
# ----------------------------------------------------------------------
audio_file = st.file_uploader(
    "🎵  Upload an audio file",
    type=["mp3", "wav", "m4a", "ogg", "flac"],
    key="audio",
)
image_files = st.file_uploader(
    "🖼️  Upload one or more images",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
    key="images",
)

# ----------------------------------------------------------------------
# Order selection (descending by default)
# ----------------------------------------------------------------------
order = st.radio(
    "🔽  Order of images in the video",
    ["Descending (last uploaded first)", "Ascending (as uploaded)"],
    index=0,  # default descending
)

# ----------------------------------------------------------------------
# Generate button
# ----------------------------------------------------------------------
if st.button("🎥  Generate Video", type="primary"):
    if not audio_file:
        st.error("❌  Please upload an audio file.")
    elif not image_files:
        st.error("❌  Please upload at least one image.")
    else:
        # Create a temporary directory to store uploaded files
        with tempfile.TemporaryDirectory() as tmpdir:
            # ---- Save audio ----
            audio_ext = os.path.splitext(audio_file.name)[1]
            audio_path = os.path.join(tmpdir, f"audio{audio_ext}")
            with open(audio_path, "wb") as f:
                f.write(audio_file.getbuffer())

            # ---- Save images and build list of paths ----
            image_paths = []
            for i, img_file in enumerate(image_files):
                img_ext = os.path.splitext(img_file.name)[1]
                img_path = os.path.join(tmpdir, f"image_{i}{img_ext}")
                with open(img_path, "wb") as f:
                    f.write(img_file.getbuffer())
                image_paths.append(img_path)

            # ---- Apply order ----
            if order.startswith("Descending"):
                image_paths = image_paths[::-1]  # reverse list

            # ---- Read audio duration ----
            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration
            n_images = len(image_paths)
            clip_duration = total_duration / n_images

            st.info(
                f"⏱️  Audio length: **{total_duration:.2f} s**  •  "
                f"Images: **{n_images}**  •  "
                f"Each image: **{clip_duration:.2f} s**"
            )

            # ---- Constants for the output video ----
            TARGET_W, TARGET_H = 1920, 1080
            FPS = 24
            ZOOM_FACTOR = 0.04  # 4% zoom over the clip duration
            BITRATE = "5000k"   # high quality for 1080p

            clips = []
            with st.spinner("🔄  Rendering video... This may take a while."):
                try:
                    for img_path in image_paths:
                        # Get original image size
                        with Image.open(img_path) as img:
                            img_w, img_h = img.size

                        # Scale factor to cover the target frame completely
                        scale = max(TARGET_W / img_w, TARGET_H / img_h)
                        base_w = int(img_w * scale)
                        base_h = int(img_h * scale)

                        # Black background clip for the target size
                        background = ColorClip(
                            size=(TARGET_W, TARGET_H),
                            color=(0, 0, 0),
                            duration=clip_duration,
                        )

                        # Image clip, resized to cover the frame
                        image_clip = (
                            ImageClip(img_path)
                            .set_duration(clip_duration)
                            .resize(newsize=(base_w, base_h))
                        )

                        # Ken Burns effect: progressive zoom in
                        def zoom_effect(t):
                            return 1.0 + ZOOM_FACTOR * t / clip_duration

                        zoomed_clip = image_clip.resize(zoom_effect).set_position("center")

                        # Compose over the black background to force 1920x1080
                        composite = CompositeVideoClip([background, zoomed_clip])
                        clips.append(composite)

                    # Concatenate all image clips
                    final_video = concatenate_videoclips(clips, method="compose")
                    final_video = final_video.set_audio(audio_clip)

                    # Write the final video file
                    output_path = os.path.join(tmpdir, "output.mp4")
                    final_video.write_videofile(
                        output_path,
                        codec="libx264",
                        audio_codec="aac",
                        fps=FPS,
                        bitrate=BITRATE,
                        preset="medium",
                        threads=2,
                        logger=None,  # suppress console logs from moviepy
                    )

                finally:
                    # Clean up resources
                    audio_clip.close()
                    final_video.close()
                    for c in clips:
                        c.close()

                # ---- Provide download button ----
                with open(output_path, "rb") as f:
                    video_bytes = f.read()
                st.success("✅  Video generated! Click the button below to download.")
                st.download_button(
                    label="⬇️  Download Video",
                    data=video_bytes,
                    file_name="ken_burns_video.mp4",
                    mime="video/mp4",
                )
