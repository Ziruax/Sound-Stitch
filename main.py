import streamlit as st
import tempfile
import os
import warnings
from PIL import Image

# Monkey-patch to make MoviePy compatible with modern Pillow versions
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

# Suppress harmless MoviePy syntax warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="moviepy")

# ----------------------------------------------------------------------
# Streamlit page configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Audio + Images → Video",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬  Audio & Images to Video (Ken Burns)")
st.markdown(
    """
    Upload **audio** and **images**. The audio is split equally across all images,  
    and each image gets a subtle zoom‑in (Ken Burns) effect.  
    Choose the output size and image order, then generate the video.
    """
)

# ----------------------------------------------------------------------
# Output size selector
# ----------------------------------------------------------------------
size_option = st.selectbox(
    "📐  Output video size",
    ["Landscape (16:9)", "Portrait (9:16)", "Square (1:1)"],
    index=0,
)

if size_option == "Landscape (16:9)":
    TARGET_W, TARGET_H = 1920, 1080
elif size_option == "Portrait (9:16)":
    TARGET_W, TARGET_H = 1080, 1920
else:  # Square
    TARGET_W, TARGET_H = 1080, 1080

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
    "🔽  Image order in video",
    ["Descending (last uploaded first)", "Ascending (as uploaded)"],
    index=0,
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
                image_paths = image_paths[::-1]

            # ---- Read audio duration ----
            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration
            n_images = len(image_paths)
            clip_duration = total_duration / n_images

            st.info(
                f"⏱️  Audio: **{total_duration:.2f}s**  •  "
                f"Images: **{n_images}**  •  "
                f"Each: **{clip_duration:.2f}s**  •  "
                f"Output: **{TARGET_W}×{TARGET_H}**"
            )

            # ---- Constants ----
            FPS = 24
            ZOOM_FACTOR = 0.04  # 4% zoom per clip
            BITRATE = "5000k"

            clips = []
            final_video = None  # initialize to avoid NameError
            with st.spinner("🔄  Rendering video…"):
                try:
                    for img_path in image_paths:
                        # Background clip of the chosen size
                        background = ColorClip(
                            size=(TARGET_W, TARGET_H),
                            color=(0, 0, 0),
                            duration=clip_duration,
                        )

                        # Image clip (no pre‑scaling – original size)
                        image_clip = ImageClip(img_path).set_duration(clip_duration)

                        # Ken Burns zoom effect
                        def zoom_effect(t):
                            return 1.0 + ZOOM_FACTOR * t / clip_duration

                        zoomed_clip = image_clip.resize(zoom_effect).set_position("center")

                        composite = CompositeVideoClip([background, zoomed_clip])
                        clips.append(composite)

                    # Concatenate all clips
                    final_video = concatenate_videoclips(clips, method="compose")
                    final_video = final_video.set_audio(audio_clip)

                    # Write the final video
                    output_path = os.path.join(tmpdir, "output.mp4")
                    final_video.write_videofile(
                        output_path,
                        codec="libx264",
                        audio_codec="aac",
                        fps=FPS,
                        bitrate=BITRATE,
                        preset="medium",
                        threads=2,
                        logger=None,
                    )

                except Exception as e:
                    st.error(f"❌  Error during video generation: {e}")
                finally:
                    # Clean up resources safely
                    if audio_clip:
                        audio_clip.close()
                    if final_video:
                        final_video.close()
                    for c in clips:
                        c.close()

            # ---- Provide download (only if video was created) ----
            if final_video and os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    video_bytes = f.read()
                st.success("✅  Video generated! Click the button below to download.")
                st.download_button(
                    label="⬇️  Download Video",
                    data=video_bytes,
                    file_name="ken_burns_video.mp4",
                    mime="video/mp4",
                )
