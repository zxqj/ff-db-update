delete from player_games where (player_id, game_id) in (select player_id,game_id from
 (select count(*) as cnt, player_id, game_id from player_games group by player_id, game_id) where cnt > 1);