import sys, os, decimal, pprint, re
import spotipy
import spotipy.util as util
from apiclient.discovery import build

TWOPLACES = decimal.Decimal('0.01')

client_id = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
client_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
redirect_uri = 'http://localhost:8888/callback'
scope = 'user-library-read'


if len(sys.argv) > 1:
    username = sys.argv[1]
else:
    username = 'slimeshady'

token = util.prompt_for_user_token(username,
                                   scope,
                                   client_id=client_id,
                                   client_secret=client_secret,
                                   redirect_uri=redirect_uri)

if token:
    sp = spotipy.Spotify(auth=token)
    tracklist = sp.current_user_saved_tracks()
    total = int(tracklist['total'])
    x = 0

    results = {'items':[]}

    while True:
        for item in tracklist['items']:
            track = item['track']

            # Math to calculate track length in minutes:seconds format
            duration = decimal.Decimal(track['duration_ms'] / 1000 / 60).quantize(TWOPLACES)
            minutes = str(duration)[0]
            sec_pct = str(duration)[1:4]
            seconds = str(decimal.Decimal(float(sec_pct) * .6).quantize(TWOPLACES,
                                                                        rounding='ROUND_DOWN'))[2:4]

            # Metadata variables extracted from Spotify API
            track_name = track['name']
            track_artist = track['artists'][0]['name']
            track_length = str(minutes + ':' + seconds)
            track_id = track['id']
        
            results['items'].append(
                {'track':
                 {'name':track_name,
                  'artist':track_artist,
                  'length':track_length,
                  'id':{'spotify':track_id}
                  }
                 }
                )
            
        if len(results['items']) == total:
            break
        else:
            x += 20
            tracklist = sp.current_user_saved_tracks(offset = x)

                
else:
    print("Can't get token for", username)


'''
    At this point we should have a data structure "results" containing information
    from my spotify saved tracks.

    Information is stored in the format:

    {'items': [{'track': {'artist': ...,
                          'id': {'spotify': ...},
                          'length': ...,
                          'name': ...}
                          },
               {'track': {...
               ....
               ..
               ...
                      ....'name': ...}
                          }
                        ]
                       }

    Where 'items' will always be the first key used to access stored metadata, and
    its value is a list of 'track' dictionaries each containing unique track metadata.
    Tracks are added to the 'items' list in reverse chronological order.

    Example:

        results['items'][0]['track']['name']  -  returns the name of the first song in
                                                 the list (newest to spotify playlist)

    Note: As opposed to its sibling keys, the 'id' key returns a dictionary containing
          the track's id tags for multiple sources (spotify, youtube, soundcloud, etc.)

          Obviously, we got the spotify ids when we pulled the playlist and track info
          from spotify in the code above.

          Code for youtube id retrieval below.
'''



DEVELOPER_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)

# temporary section for testing purposes
youtube_results = {'items': {}}
count = 0

while count < 10:
    spot_id = results['items'][count]['track']['id']['spotify']
    query = (results['items'][count]['track']['artist'] + ' - ' + results['items'][count]['track']['name'])

    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=5
        ).execute()

    youtube_results['items'][spot_id] = []
    youtube_ids = []
    
    for search_result in search_response.get("items", []):
        if search_result['id']['kind'] == "youtube#video":
            youtube_results['items'][spot_id].append([search_result['id']['videoId'],
                                                      search_result['snippet']['title'],
                                                      search_result['snippet']['channelTitle']
                                                      ]
                                                     )
            youtube_ids.append(search_result['id']['videoId'])

    video_ids = ','.join(youtube_ids)
    video_response = youtube.videos().list(
        id=video_ids,
        part='contentDetails'
        ).execute()

    subcount = 0
    for video_result in video_response.get('items', []):
        youtube_results['items'][spot_id][subcount].append(video_result['contentDetails']['duration'])
        subcount += 1

    youtube_results['items'][spot_id].append(count)
    count += 1

def rank_reducer(all_ranks, current_rank):
    try:
        return (all_ranks.index(current_rank), current_rank)
    except ValueError:
        current_rank -= 1
        return rank_reducer(all_ranks, current_rank)
        
for s_id in youtube_results['items'].keys():
    num = len(youtube_results['items'][s_id]) - 1
    for y_index in range(num):
        time_string = youtube_results['items'][s_id][y_index].pop()
        regex = r"^PT(\d\d?)(H|M|S)(\d\d?)?(M|S)?((\d\d?)S)?$"
        research = re.search(regex, time_string)
        mins = research.group(1)
        if not research.group(3):
            secs = '00'
        else:
            secs = research.group(3) if len(research.group(3)) == 2 else ('0%s' % research.group(3))
        y_length = '%s:%s' % (mins,secs)
        youtube_results['items'][s_id][y_index].append(y_length)
        
    data_dict = {'youtube_ids':[youtube_results['items'][s_id][x][0] for x in range(num)],
                 'youtube_titles':[youtube_results['items'][s_id][x][1] for x in range(num)],
                 'youtube_channels':[youtube_results['items'][s_id][x][2] for x in range(num)],
                 'youtube_times':[youtube_results['items'][s_id][x][3] for x in range(num)]}

    s_index = youtube_results['items'][s_id][num]
    s_length = results['items'][s_index]['track']['length']
    s_mins, s_secs = s_length.split(':')
    s_artist = results['items'][s_index]['track']['artist']

    y_TitleCase = s_artist.title().replace(' ','')
    y_CAPS = s_artist.upper().replace(' ','')
    y_lower = s_artist.lower().replace(' ','')

    rank_list = [str(x*0) for x in range(num)]
    channel_index = 0
    for ydata in data_dict['youtube_channels']:
        int_rank = int(rank_list[channel_index])
        if (y_TitleCase in ydata) or (y_CAPS in ydata) or (y_lower in ydata):
            if int_rank == 0:
                int_rank += 1
                rank_list[channel_index] = str(int_rank)
        elif ydata == '':
            int_rank -= 1
            rank_list[channel_index] = str(int_rank)
        channel_index += 1

    time_index = 0    
    for ydata in data_dict['youtube_times']:
        y_mins,y_secs = ydata.split(':')
        int_rank = int(rank_list[time_index])
        if y_mins == s_mins and (abs(int(y_secs) - int(s_secs)) <= 3):
            int_rank += 1
            rank_list[time_index] = str(int_rank)
        time_index += 1

    title_index = 0
    regex_list = [r" hq ?",
                  r" ?high quality ?",
                  r" ?\( ?hq ?\) ?",
                  r" ?\( ?high quality ?\) ?",
                  r" ?\[ ?hq ?\] ?",
                  r" ?\[ ?high quality ?\] ?"
                  ]
    for ydata in data_dict['youtube_titles']:
        int_rank = int(rank_list[title_index])
        #if (' hq ' in ydata.lower()) or (' high quality ' in ydata.lower()):

        for regex in regex_list:
            research = re.search(regex, ydata.lower())
            if research:
                int_rank += 1
                rank_list[title_index] = str(int_rank)
                break
        title_index += 1
    
    rank_list = [int(x) for x in rank_list]
    
    rank_index, rank = rank_reducer(rank_list, 3)
       
    youtube_results['items'][s_id] = youtube_results['items'][s_id][rank_index]
    results['items'][s_index]['track']['id']['youtube'] = youtube_results['items'][s_id][0]

    pprint.pprint(rank_list)
    pprint.pprint(data_dict)

#pprint.pprint(youtube_results)
#print('\n\n')
#pprint.pprint(results)

'''
    outliers and curiosities:
        '7DZILA0M4ZbMw3LdibHMcg': ['_AaHumrLfuU',
                                      'Bryce - Freefall Anthem',
                                      'Planetpunkmusic',
                                      '3:20'],
        '7CZL5uoY1KkzZiXnsgLuYg': ['hQfeDHeksXY',
                                      'To Life (Radio Edit)',
                                      '',
                                      '3:03'],
        '6r7FXNO57mlZCBY6PXcZZT': ['K_yBUfMGvzc',
                                      'Deorro - Five Hours (Static Video) '
                                      '[LE7ELS]',
                                      'LE7ELSOfficial',
                                      '5:30'],
        '6pNBH4KKQYVRtgXNrINq1w': ['_J4bZp6pqJo',
                                      'M83 - Midnight City (Eric Prydz '
                                      'Remix) HD HQ',
                                      'HouseMusicFix',
                                      '6:38'],
        '68PDydciw4W2e16wCbr9tv': ['BkzvSf9NLTY',
                                      'Infinity Ink - Infinity (Original '
                                      'Mix)',
                                      'TheIoLoSo5',
                                      '5:10'],
        '4p2GmWPZRK9zYAp7I57WOL': ['wPaosKdSgPI',
                                      'Richard Vission & Nghtmre feat. '
                                      'Jackie Boyz - Walking On Sunshine '
                                      '(Original Mix)',
                                      'EDMLOfficial',
                                      '4:55'],
        '4KtrE35pTuqwNc22QP58RT': ['6vopR3ys8Kw',
                                      'Flume & Chet Faker - Drop the Game '
                                      '[Official Music Video]',
                                      'futureclassic',
                                      '4:10'],
        '3qW6Myx89J3qtUr12twBKs': ['2Rxa4pNAnMY',
                                      'The Griswolds - Live This Nightmare '
                                      '(NGHTMRE Remix) [Free]',
                                      'PandoraMuslc',
                                      '3:30'],
        '30VOz9BAQ9V2k355ya3q4X': ['K8IQKMRh9n8',
                                      'Mount Dreams - Home (ft. Anatomy)',
                                      'SpinninRec',
                                      '4:35'],
        '0TwsfroKu7M2aCSGOKfnoK': ['KTvfwd3JZTE',
                                      'Feed Me & Kill The Noise - Far Away '
                                      '(Official Music Video)',
                                      'youfeedme',
                                      '4:07'],
        
    10/59 correct
    83% accuracy
    1st run
'''
