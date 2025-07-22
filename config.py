# Dynamic services that require IP testing
DYNAMIC_SERVICES = {
    'Microsoft_Account': {
        'name': 'Microsoft Account',
        'ip_file': 'Microsoft_Account.txt',
        'domains': ['account.microsoft.com']
    },
    'Xbox_Live_CDN_1': {
        'name': 'Xbox Live CDN',
        'ip_file': 'Xbox_Live_CDN_1.txt',
        'domains': [
            'gameclipscontent-d2009.xboxlive.com',
            'images-eds.xboxlive.com',
            'xbl-smooth.xboxlive.com',
            'titlehub.xboxlive.com',
            'compass.xboxlive.com',
            'xnotify.xboxlive.com',
            'activityhub.xboxlive.com',
            'xboxcare.xboxlive.com',
            'images-eds-ssl.xboxlive.com',
            'rta.xboxlive.com',
            'peoplehub.xboxlive.com',
            'editorial.xboxlive.com'
        ]
    },
    'Xbox_Live_CDN_2': {
        'name': 'Xbox Live CDN 2',
        'ip_file': 'Xbox_Live_CDN_2.txt',
        'domains': []  # Reserved for future use
    },
    'Xbox_Cloud_Sync': {
        'name': 'Xbox Cloud Sync',
        'ip_file': 'Xbox_Cloud_Sync.txt',
        'domains': ['titlestorage.xboxlive.com']
    },
    'Office_CDN': {
        'name': 'Office CDN',
        'ip_file': 'Office_CDN.txt',
        'domains': ['officecdn.microsoft.com']
    },
    'Microsoft_Store_Images': {
        'name': 'Microsoft Store Images',
        'ip_file': 'Microsoft_Store_Images.txt',
        'domains': ['store-images.s-microsoft.com']
    },
    'Microsoft_Store_Pages': {
        'name': 'Microsoft Store Pages',
        'ip_file': 'Microsoft_Store_Pages.txt',
        'domains': ['storeedgefd.dsx.mp.microsoft.com']
    },
    'Microsoft_Games_Download': {
        'name': 'Microsoft Games Download',
        'ip_file': 'Microsoft_Games_Download.txt',
        'domains': ['xvcf1.xboxlive.com', 'xvcf2.xboxlive.com']
    },
    'Windows_Update': {
        'name': 'Windows Update',
        'ip_file': 'Windows_Update.txt',
        'domains': [
            'tlu.dl.delivery.mp.microsoft.com',
            'dl.delivery.mp.microsoft.com',
            'assets1.xboxlive.cn',
            'assets2.xboxlive.cn'
        ]
    },
    # Example of how to add a new service:
    # 'OneNote': {
    #     'name': 'OneNote',
    #     'ip_file': 'OneNote.txt',
    #     'domains': ['www.onenote.com', 'onenote.com']
    # }
}

# Static services with predefined IP addresses
STATIC_SERVICES = {
    'Microsoft_Login': {
        'name': 'Microsoft Login',
        'ip': '13.107.42.22',
        'domains': [
            'logincdn.msauth.net',
            'login.live.com',
            'acctcdn.msauth.net',
            'account.live.com'
        ]
    }
}

# Special custom entries that don't follow the standard format
CUSTOM_ENTRIES = {
    'OneDrive_China': {
        'name': 'OneDrive (Beta, only for China)',
        'entries': [
            '134.170.108.26 onedrive.live.com',
            '134.170.109.48 skyapi.onedrive.live.com'
        ]
    }
}

# Default configuration settings
DEFAULT_CONFIG = {
    'data_directory': './data',
    'output_file': 'hosts',
    'ping_attempts': 2,  # ping次数
    'ping_timeout': 0.5,  # ping超时时间
    'ping_max_workers': 100,  # 异步并发数量
    'good_enough_threshold': 50.0,  # 延迟阈值（毫秒）
    'max_workers': None  # CPU核心数（None表示使用默认值）
}
