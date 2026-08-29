#!/usr/bin/env perl

use strict;
use warnings;

use LWP::UserAgent;
use JSON qw(decode_json);
use XML::Writer;
use IO::File;
use POSIX qw(strftime);

binmode(STDOUT, ':encoding(UTF-8)');
binmode(STDERR, ':encoding(UTF-8)');

#------------------------------------------------------------
# Configuration
#------------------------------------------------------------

my $CLIENT_ID = $ENV{"SOUNDCLOUD_CLIENT_ID"};
my $USER_ID = "19053868";
my $OUTPUT = "yonder.xml";

my $API_URL = "https://api-v2.soundcloud.com/users/$USER_ID/tracks";

#------------------------------------------------------------
# Validate configuration
#------------------------------------------------------------

unless (defined $CLIENT_ID && length $CLIENT_ID) {
print STDERR "ERROR 41: SOUNDCLOUD_CLIENT_ID is not set\n";
exit 41;
}

#------------------------------------------------------------
# HTTP client
#------------------------------------------------------------

my $ua = LWP::UserAgent->new(
   agent => "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
   timeout => 30,
);

$ua->default_header(
   "Accept" => "application/json",
   "Referer" => "https://soundcloud.com/yondertapes",
);

#------------------------------------------------------------
# Fetch all SoundCloud tracks
#------------------------------------------------------------

my @tracks;
my %seen_ids;

my $url = $API_URL;
my $first_request = 1;
my $page = 0;

while ($url) {

$page++;

print "FETCH PAGE $page\n";
print "URL: $url\n";

my $request_url = $url;

if ($request_url =~ /\?/) {
    $request_url .= "&client_id=$CLIENT_ID";
} else {
    $request_url .= "?client_id=$CLIENT_ID";
}

if ($first_request) {
    $request_url .= "&limit=50";
    $first_request = 0;
}

my $response = $ua->get($request_url);

print "STATUS: ", $response->code, "\n";

unless ($response->is_success) {
    print STDERR "ERROR 42: SoundCloud API request failed\n";
    print STDERR "HTTP STATUS: ", $response->code, "\n";
    print STDERR $response->decoded_content, "\n";
    exit 42;
}

my $data;

eval {
    $data = decode_json($response->decoded_content);
};

if ($@ || !defined $data) {
    print STDERR "ERROR 43: SoundCloud returned invalid JSON\n";
    print STDERR $response->decoded_content, "\n";
    exit 43;
}

my $collection = $data->{collection};

unless (ref($collection) eq "ARRAY") {
    print STDERR "ERROR 44: SoundCloud response has no collection\n";
    exit 44;
}

print "THIS PAGE: ", scalar(@$collection), "\n";

for my $track (@$collection) {

    next unless ref($track) eq "HASH";

    my $id = $track->{id};

    next unless defined $id;
    next if $seen_ids{$id};

    $seen_ids{$id} = 1;
    push @tracks, $track;
}

$url = $data->{next_href};

if ($url) {
    print "NEXT PAGE AVAILABLE\n";
}
else {
    print "NO NEXT PAGE\n";
}


}

#------------------------------------------------------------
# Validate tracks
#------------------------------------------------------------

unless (@tracks) {
print STDERR "ERROR 45: No SoundCloud tracks found\n";
exit 45;
}

print "TOTAL TRACKS: ", scalar(@tracks), "\n";

#------------------------------------------------------------
# Sort newest first
#------------------------------------------------------------

@tracks = sort {
($b->{created_at} || "") cmp
($a->{created_at} || "")
} @tracks;

#------------------------------------------------------------
# Open RSS output
#------------------------------------------------------------

my $output = IO::File->new(">$OUTPUT");

unless ($output) {
print STDERR "ERROR 46: Cannot open $OUTPUT for writing: $!\n";
exit 46;
}

#------------------------------------------------------------
# Create RSS
#------------------------------------------------------------

my $writer = XML::Writer->new(
OUTPUT => $output,
DATA_MODE => 1,
DATA_INDENT => 2,
);

$writer->startTag(
"rss",
version => "2.0",
);

$writer->startTag("channel");

$writer->dataElement(
"title",
"Yonder",
);

$writer->dataElement(
"link",
"https://soundcloud.com/yondertapes",
);

$writer->dataElement(
"description",
"Yonder SoundCloud tracks and DJ sets.",
);

$writer->dataElement(
"language",
"en",
);

$writer->dataElement(
"generator",
"Yonder RSS Bot",
);

$writer->dataElement(
"lastBuildDate",
strftime(
"%a, %d %b %Y %H:%M:%S +0000",
gmtime()
),
);

#------------------------------------------------------------
# RSS items
#------------------------------------------------------------

for my $track (@tracks) {

my $title =
    $track->{title} || "Untitled";

my $track_url =
    $track->{permalink_url} || "";

my $description =
    $track->{description} || "";

my $created_at =
    $track->{created_at} || "";

$writer->startTag("item");

$writer->dataElement(
    "title",
    $title,
);

$writer->dataElement(
    "link",
    $track_url,
);

$writer->startTag(
    "guid",
    isPermaLink => "true",
);

$writer->characters($track_url);

$writer->endTag("guid");

$writer->dataElement(
    "description",
    $description,
);

if ($created_at) {

    my $pub_date = $created_at;

    if (
        $created_at =~
        /^(\d{4})-(\d{2})-(\d{2})T
         (\d{2}):(\d{2}):(\d{2})\.?\d*Z$/x
    ) {

        my (
            $year,
            $month,
            $day,
            $hour,
            $minute,
            $second
        ) = ($1, $2, $3, $4, $5, $6);

        my @months =
            qw(
                Jan Feb Mar Apr May Jun
                Jul Aug Sep Oct Nov Dec
            );

        $pub_date = sprintf(
            "%02d %s %04d %02d:%02d:%02d +0000",
            $day,
            $months[$month - 1],
            $year,
            $hour,
            $minute,
            $second
        );

        $pub_date =
            "Thu, $pub_date";
    }

    $writer->dataElement(
        "pubDate",
        $pub_date,
    );
}

$writer->endTag("item");


}

#------------------------------------------------------------
# Finish XML
#------------------------------------------------------------

$writer->endTag("channel");
$writer->endTag("rss");
$writer->end();

$output->close();

#------------------------------------------------------------
# Final validation
#------------------------------------------------------------

unless (-s $OUTPUT) {
print STDERR "ERROR 47: $OUTPUT was not created or is empty\n";
exit 47;
}

print "RSS GENERATED SUCCESSFULLY\n";
print "TRACKS: ", scalar(@tracks), "\n";
print "FILE: $OUTPUT\n";

exit 0;
