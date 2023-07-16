import aiohttp.web, asyncio, bs4, urllib.parse, fake_useragent, tempfile, sys, re, huggingface_hub, pathlib, builtins, zhconv, argparse

parser = argparse.ArgumentParser()
parser.add_argument('huggingface')

huggingface_hub.login(parser.parse_args().huggingface) #https://huggingface.co/settings/tokens
unlink = []

async def main():
    app = aiohttp.web.Application()
    app.add_routes([aiohttp.web.static('/', pathlib.Path(__file__).parent)])
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    async with aiohttp.ClientSession(headers={'user-agent':fake_useragent.UserAgent().chrome}) as client:
        async with client.get('https://myself-bbs.com/forum.php?mod=viewthread&tid=49519&extra=page%3D1%26filter%3Dtypeid%26typeid%3D139%26typeid%3D139') as episode:
            html = bs4.BeautifulSoup(await episode.text(), 'lxml')
            title = zhconv.convert(html.find('title').string.split('【')[0], 'zh-cn')
            for _ in html.find('ul', attrs={'class', 'main_list'}).find_all('li', recursive=False):
                async with client.ws_connect('wss://v.myself-bbs.com/ws') as ws:
                    await ws.send_json({'tid':'','vid':'','id':urllib.parse.urlparse(_.find('a', attrs={'data-href':True}).get('data-href')).path.split('/')[-1]})
                    video = 'https:' + (await ws.receive_json()).get('video')
                    async with client.get(video, headers={'referer':'https://v.myself-bbs.com'}) as m3u8:
                        pathlib.Path('index.m3u8').write_bytes(re.sub(b'^\d+\.ts$', lambda _:b'/'.join((video.rsplit('/', 1)[0].encode(),  _.group(0))), await m3u8.content.read(), flags=re.MULTILINE))
                        with tempfile.NamedTemporaryFile(delete=False) as tmp:
                            sys.modules[__name__].unlink += tmp.name,
                            ffmpeg = await asyncio.create_subprocess_exec('ffmpeg', '-y', '-headers', 'referer:https://v.myself-bbs.com', '-protocol_whitelist', 'pipe,https,tls,tcp,http', '-i', 'http://localhost:8000/index.m3u8', '-f', 'mp4', tmp.name)
                            await ffmpeg.wait()
                            api = huggingface_hub.HfApi()
                            api.upload_file(path_or_fileobj=tmp.name, path_in_repo=''.join((title, '/', _.find('a', attrs={'href':'javascript:;'}).string.split()[1], '.mp4')), repo_id='chaowenguo/video', repo_type='model', run_as_future=True)

asyncio.run(main())
for _ in unlink: os.unlink(_)
