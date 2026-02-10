export interface Author {
  id: number;
  name: string;
}

export interface Publisher {
  id: number;
  name: string;
}

export interface Genre {
  id: number;
  name: string;
}

export interface Critic {
  id: number;
  name: string;
}

export interface Publication {
  id: number;
  name: string;
}

export interface Review {
  id: number;
  book_id: number;
  rating: number;
  review: string;
  url: string | null;
  critic: Critic | null;
  publication: Publication | null;
}

export interface Book {
  id: number;
  title: string;
  author_id: number | null;
  publisher_id: number | null;
  publish_date: string | null;
  description: string;
  url: string;
  cover: string | null;
  author: Author | null;
  publisher: Publisher | null;
  genres: Genre[];
  avg_critic_rating: number | null;
  review_count: number;
}

export interface UserRating {
  id: number;
  user_id: number;
  book_id: number;
  rating: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface UserPublic {
  id: number;
  username: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
}

export interface RatingCreate {
  book_id: number;
  rating: number;
}

export type BookSortOption =
  | "title_asc"
  | "title_desc"
  | "date_desc"
  | "date_asc"
  | "rating_desc"
  | "reviews_desc";

export type RecommendationCategory = "fiction" | "nonfiction" | "all";
export type RecommendationStrategy = "personalized" | "popular";

export interface RecommendationMeta {
  strategy: RecommendationStrategy;
  rating_count: number;
  category: RecommendationCategory;
}

export interface RecommendationResponse {
  items: Book[];
  meta: RecommendationMeta;
}

export interface UserProfile {
  id: number;
  username: string;
  rating_count: number;
}
