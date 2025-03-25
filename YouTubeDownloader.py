import aiohttp
import asyncio
import io
import subprocess
import os
from hikka import loader, utils
from telethon.tl.types import Message, DocumentAttributeVideo

__version__ = (1, 0, 0)

#       █████  ██████   ██████ ███████  ██████  ██████   ██████ 
#       ██   ██ ██   ██ ██      ██      ██      ██    ██ ██      
#       ███████ ██████  ██      █████   ██      ██    ██ ██      
#       ██   ██ ██      ██      ██      ██      ██    ██ ██      
#       ██   ██ ██       ██████ ███████  ██████  ██████   ██████
#
#              © Copyright 2025
#           https://t.me/apcecoc
#
# 🔒      Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @apcecoc
# scope: hikka_only
# scope: hikka_min 1.2.10

@loader.tds
class YouTubeDownloaderMod(loader.Module):
    """Module for downloading YouTube videos via PaxSenix API"""


    strings = {
        "name": "YouTubeDownloader",
        "no_url": "❌ Please provide a video URL! Example: .ytdl https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "fetching_qualities": "⏳ Fetching available video resolutions...",
        "select_quality": "🎥 Select the quality to download:\n\n{qualities}",
        "invalid_quality": "❌ The selected quality is not available! Please try again.",
        "processing": "⏳ Processing video in {quality} quality...",
        "loading_animation": "⏳ Loading... ({seconds} sec)",
        "download_success": "✅ Video downloaded successfully!\n\n🎬 Title: {title}\n📏 Size: {size} MB\n📐 Resolution: {resolution}",
        "failed": "❌ Error: {error}. Retrying...",
        "max_retries": "❌ Maximum retry attempts reached. Please try again later.",
        "download_failed": "❌ Failed to download the video.",
        "api_error": "❌ API error: {error}",
        "invalid_response": "❌ API returned an invalid response (possibly HTML). Please try again later.",
        "format_warning": "⚠️ If the video doesn't play, it may be due to an unsupported codec (e.g., VP9). Try a different quality or use an external player."
        "_cls_doc" = "Downloads YouTube videos in various qualities directly to the chat."
    }

    strings_ru = {
        "name": "YouTubeDownloader",
        "_cls_doc": "Скачивание видео с YouTube в различных качествах прямо в чат.",
        "no_url": "❌ Пожалуйста, укажите URL видео! Пример: .ytdl https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "fetching_qualities": "⏳ Получаю доступные разрешения для видео...",
        "select_quality": "🎥 Выберите качество для скачивания:\n\n{qualities}",
        "invalid_quality": "❌ Выбранное качество недоступно! Попробуйте снова.",
        "processing": "⏳ Обрабатываю видео в качестве {quality}...",
        "loading_animation": "⏳ Загрузка... ({seconds} сек)",
        "download_success": "✅ Видео успешно загружено!\n\n🎬 Название: {title}\n📏 Размер: {size} MB\n📐 Разрешение: {resolution}",
        "failed": "❌ Ошибка: {error}. Пробую снова...",
        "max_retries": "❌ Максимальное количество попыток достигнуто. Попробуйте позже.",
        "download_failed": "❌ Не удалось скачать видео.",
        "api_error": "❌ Ошибка API: {error}",
        "invalid_response": "❌ API вернул некорректный ответ (возможно, HTML). Попробуйте позже.",
        "format_warning": "⚠️ Если видео не воспроизводится, это связано с неподдерживаемым кодеком (например, VP9). Попробуйте другое качество или используйте сторонний плеер."
    }

    def __init__(self):
        self.base_url = "https://api.paxsenix.biz.id"
        self.session = None
        self.max_retries = 3  # Maximum retry attempts for "failed" status
        self.task_retries = 3  # Maximum retry attempts for /task/{jobId} requests

    async def client_ready(self, client, db):
        """Client initialization"""
        self.client = client
        self.db = db
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def on_unload(self):
        """Close the session when unloading the module"""
        if self.session:
            await self.session.close()

    def get_video_resolution(self, video_content: io.BytesIO) -> str:
        """Get video resolution using ffprobe (if available)"""
        try:
            # Save the video to a temporary file
            temp_filename = "temp_video.mp4"
            with open(temp_filename, "wb") as f:
                f.write(video_content.getvalue())

            # Use ffprobe to get metadata
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", temp_filename],
                capture_output=True,
                text=True
            )
            metadata = eval(result.stdout)  # Parse ffprobe JSON output
            width = metadata["streams"][0]["width"]
            height = metadata["streams"][0]["height"]
            os.remove(temp_filename)  # Delete the temporary file
            return f"{width}x{height}"
        except Exception as e:
            return "Unknown"

    def estimate_dimensions(self, quality: str) -> tuple:
        """Estimate width and height based on selected quality"""
        quality = quality.lower().replace("p", "")
        dimensions = {
            "144": (256, 144),
            "240": (426, 240),
            "360": (640, 360),
            "480": (854, 480),
            "720": (1280, 720),
            "1080": (1920, 1080),
            "1440": (2560, 1440),
            "2160": (3840, 2160)
        }
        return dimensions.get(quality, (1280, 720))  # Default to 720p

    async def download_video(self, url: str, title: str, call) -> io.BytesIO:
        """Download video by URL without progress display"""
        async with self.session.get(url, timeout=600) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            video_content = io.BytesIO()

            async for chunk in response.content.iter_chunked(1024 * 1024):
                if chunk:
                    downloaded += len(chunk)
                    video_content.write(chunk)

            video_content.seek(0)
            video_content.name = f"{title}.mp4"  # Add .mp4 extension
            return video_content, downloaded

    async def get_available_qualities(self, youtube_url: str) -> list:
        """Get the list of available video resolutions"""
        url = f"{self.base_url}/dl/ytmp4"
        params = {"url": youtube_url}

        async with self.session.get(url, params=params) as response:
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' not in content_type:
                return []

            data = await response.json()
            if not data.get("ok") and "qualities" in data:
                return data["qualities"]
            return []

    async def start_download(self, youtube_url: str, quality: str) -> dict:
        """Start downloading the video with the specified quality"""
        url = f"{self.base_url}/dl/ytmp4"
        params = {"url": youtube_url, "quality": quality}

        async with self.session.get(url, params=params) as response:
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' not in content_type:
                return None

            data = await response.json()
            if data.get("ok"):
                return {
                    "jobId": data.get("jobId"),
                    "task_url": data.get("task_url")
                }
            return None

    async def check_task_status(self, task_url: str, call) -> dict:
        """Check task status with a loading animation"""
        seconds = 0
        attempt = 0

        while attempt < self.task_retries:
            try:
                async with self.session.get(task_url, timeout=30) as response:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        await call.edit(self.strings["invalid_response"])
                        attempt += 1
                        await asyncio.sleep(5)
                        continue

                    data = await response.json()

                    if data.get("status") == "pending":
                        await call.edit(
                            self.strings["loading_animation"].format(seconds=seconds)
                        )
                        await asyncio.sleep(7)
                        seconds += 7
                    elif data.get("status") == "done":
                        return {
                            "success": True,
                            "title": data["info"]["title"],
                            "url": data["url"]
                        }
                    elif data.get("status") == "failed":
                        return {
                            "success": False,
                            "error": data.get("result", "Unknown error")
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Unknown task status"
                        }

            except aiohttp.ClientError as e:
                attempt += 1
                await call.edit(self.strings["api_error"].format(error=str(e)))
                if attempt < self.task_retries:
                    await asyncio.sleep(5)
                continue

        return {
            "success": False,
            "error": "Maximum retry attempts for status check reached"
        }

    @loader.command()
    async def ytdl(self, message: Message):
        """Download a video from YouTube. Usage: .ytdl <url>"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_url"])
            return

        youtube_url = args.strip()
        await utils.answer(message, self.strings["fetching_qualities"])

        qualities = await self.get_available_qualities(youtube_url)
        if not qualities:
            await utils.answer(message, "❌ Failed to fetch available resolutions!")
            return

        markup = []
        for q in qualities:
            markup.append([{
                "text": f"{q}p",
                "callback": self.ytdl_select,
                "args": (q, youtube_url)
            }])

        await self.inline.form(
            message=message,
            text=self.strings["select_quality"].format(qualities="\n".join(f"- {q}p" for q in qualities)),
            reply_markup=markup
        )

    async def ytdl_select(self, call, quality: str, youtube_url: str):
        """Handle quality selection"""
        await call.edit(self.strings["processing"].format(quality=quality))

        for attempt in range(self.max_retries):
            task_data = await self.start_download(youtube_url, quality)
            if not task_data:
                await call.edit("❌ Failed to start the download!")
                return

            result = await self.check_task_status(task_data["task_url"], call)
            if result["success"]:
                try:
                    # Download the video and get its size
                    video_content, size = await self.download_video(result["url"], result["title"], call)
                    # Check resolution (if ffprobe is available)
                    resolution = self.get_video_resolution(video_content)
                    video_content.seek(0)  # Reset pointer after checking

                    # Estimate width and height based on quality
                    width, height = self.estimate_dimensions(quality)

                    # Add video attributes
                    attributes = [
                        DocumentAttributeVideo(
                            duration=0,  # Duration unknown without ffprobe
                            w=width,
                            h=height,
                            supports_streaming=True
                        )
                    ]

                    # Send the video to the chat
                    await self._client.send_file(
                        call.form["chat"],
                        video_content,
                        caption=self.strings["download_success"].format(
                            title=result["title"],
                            size=size // 1024 // 1024,
                            resolution=resolution
                        ) + "\n" + self.strings["format_warning"],
                        attributes=attributes,
                        supports_streaming=True,
                        mime_type="video/mp4"
                    )
                    await call.delete()
                    return
                except Exception as e:
                    await call.edit(self.strings["download_failed"])
                    return
            else:
                await call.edit(
                    self.strings["failed"].format(error=result["error"])
                )
                if attempt == self.max_retries - 1:
                    await call.edit(self.strings["max_retries"])
                    return
                await asyncio.sleep(2)